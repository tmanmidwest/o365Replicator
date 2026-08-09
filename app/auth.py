"""Authentication: UI sessions and machine (API key / OAuth) credentials.

Design notes:
- UI routes depend on ``require_login`` which redirects to /login (or /setup when
  no admin exists yet) instead of returning a JSON 401.
- API routes depend on ``require_api_client`` which accepts ANY of: a valid UI
  session cookie (so the UI's own fetch calls work), a managed API key via the
  ``X-API-Key`` header (or the legacy static ``API_KEY`` env), or an OAuth2
  Bearer token minted at /oauth/token.
- SQLite returns naive datetimes, so all expiry math here uses naive UTC.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import security
from .config import settings
from .database import get_db
from .models import AdminUser, ApiKey, OAuthToken, UserSession

COOKIE_NAME = "o365_session"


def now_utc() -> datetime:
    """Naive UTC 'now' — matches what SQLite hands back on read."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def cookie_is_secure(request: Request) -> bool:
    """Decide the session cookie's Secure flag.

    "auto" bases it on the actual request scheme (which reflects the tunnel's
    X-Forwarded-Proto when --proxy-headers is on), so login works over both the
    https tunnel and direct-http testing. "true"/"false" force it.
    """
    mode = (settings.cookie_secure or "auto").strip().lower()
    if mode in ("true", "1", "yes", "on"):
        return True
    if mode in ("false", "0", "no", "off"):
        return False
    return request.url.scheme == "https"


# --- Admin bootstrap / lookup ---------------------------------------------------

def admin_exists(db: Session) -> bool:
    return db.execute(select(AdminUser.id).limit(1)).first() is not None


# --- Session lifecycle ----------------------------------------------------------

def create_session(db: Session, user: AdminUser) -> str:
    token = security.new_session_token()
    db.add(
        UserSession(
            token=token,
            user_id=user.id,
            expires_at=now_utc() + timedelta(hours=settings.session_ttl_hours),
        )
    )
    user.last_login_at = now_utc()
    db.commit()
    return token


def destroy_session(db: Session, token: str | None) -> None:
    if not token:
        return
    row = db.execute(select(UserSession).where(UserSession.token == token)).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()


def get_session_user(request: Request, db: Session) -> AdminUser | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    row = db.execute(select(UserSession).where(UserSession.token == token)).scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at < now_utc():
        db.delete(row)
        db.commit()
        return None
    return db.get(AdminUser, row.user_id)


# --- UI guard -------------------------------------------------------------------

def require_login(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    """Dependency for UI routes: redirect to /setup or /login rather than 401."""
    if not admin_exists(db):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/setup"})
    user = get_session_user(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


# --- Machine credential verification --------------------------------------------

def _verify_api_key(db: Session, presented: str) -> str | None:
    """Match a presented X-API-Key against managed keys, then the static env key."""
    if not presented:
        return None
    if presented.startswith("o365k_"):
        prefix = presented[:14]
        candidates = db.execute(
            select(ApiKey).where(ApiKey.prefix == prefix, ApiKey.revoked.is_(False))
        ).scalars()
        for key in candidates:
            if security.verify_secret(presented, key.key_hash):
                key.last_used_at = now_utc()
                db.commit()
                return f"apikey:{key.name}"
    if settings.api_key and security.constant_time_equals(presented, settings.api_key):
        return "apikey:static-env"
    return None


def _verify_bearer(db: Session, token: str) -> str | None:
    row = db.execute(select(OAuthToken).where(OAuthToken.token == token)).scalar_one_or_none()
    if row is None or row.expires_at < now_utc():
        return None
    return f"oauth:client#{row.client_pk}"


@dataclass
class Principal:
    kind: str  # "session" | "apikey" | "oauth"
    label: str


def require_api_client(
    request: Request,
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    """Accept a UI session, a managed/static API key, or an OAuth Bearer token."""
    # 1) Logged-in UI user (lets the dashboard's own fetch calls through).
    user = get_session_user(request, db)
    if user is not None:
        return Principal(kind="session", label=f"user:{user.username}")

    # 2) API key header.
    label = _verify_api_key(db, x_api_key or "")
    if label:
        return Principal(kind="apikey", label=label)

    # 3) OAuth2 Bearer token.
    if authorization and authorization.lower().startswith("bearer "):
        label = _verify_bearer(db, authorization[7:].strip())
        if label:
            return Principal(kind="oauth", label=label)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide a valid X-API-Key or OAuth Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
