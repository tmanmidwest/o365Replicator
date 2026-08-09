"""Web UI for authentication and credential management."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..auth import COOKIE_NAME, admin_exists, create_session, destroy_session, get_session_user, require_login
from ..config import settings
from ..database import get_db
from ..models import AdminUser, ApiKey, OAuthClient

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

_SESSION_MAX_AGE = None  # session cookie tied to server-side expiry


def _set_session_cookie(resp: RedirectResponse, token: str) -> None:
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )


# --- First-run setup ------------------------------------------------------------

@router.get("/setup", response_class=HTMLResponse)
def setup_form(request: Request, db: Session = Depends(get_db)):
    if admin_exists(db):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("setup.html", {"request": request})


@router.post("/setup")
def setup_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    if admin_exists(db):
        return RedirectResponse("/login", status_code=303)
    error = None
    if len(username.strip()) < 3:
        error = "Username must be at least 3 characters."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != confirm:
        error = "Passwords do not match."
    if error:
        return templates.TemplateResponse(
            "setup.html", {"request": request, "error": error, "username": username}, status_code=400
        )
    user = AdminUser(username=username.strip(), password_hash=security.hash_secret(password))
    db.add(user)
    db.commit()
    token = create_session(db, user)
    resp = RedirectResponse("/", status_code=303)
    _set_session_cookie(resp, token)
    return resp


# --- Login / logout -------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if not admin_exists(db):
        return RedirectResponse("/setup", status_code=303)
    if get_session_user(request, db) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.execute(
        select(AdminUser).where(AdminUser.username == username.strip())
    ).scalar_one_or_none()
    if user is None or not security.verify_secret(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password.", "username": username},
            status_code=401,
        )
    token = create_session(db, user)
    resp = RedirectResponse("/", status_code=303)
    _set_session_cookie(resp, token)
    return resp


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    destroy_session(db, request.cookies.get(COOKIE_NAME))
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


# --- Account (change password) --------------------------------------------------

@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request, user: AdminUser = Depends(require_login)):
    return templates.TemplateResponse("account.html", {"request": request, "user": user, "active": "account"})


@router.post("/account/password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm: str = Form(...),
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    ctx = {"request": request, "user": user, "active": "account"}
    if not security.verify_secret(current_password, user.password_hash):
        ctx["error"] = "Current password is incorrect."
    elif len(new_password) < 8:
        ctx["error"] = "New password must be at least 8 characters."
    elif new_password != confirm:
        ctx["error"] = "New passwords do not match."
    if "error" in ctx:
        return templates.TemplateResponse("account.html", ctx, status_code=400)
    user.password_hash = security.hash_secret(new_password)
    db.commit()
    ctx["message"] = "Password updated."
    return templates.TemplateResponse("account.html", ctx)


# --- Access & Credentials -------------------------------------------------------

def _access_context(request: Request, db: Session, user: AdminUser, **extra) -> dict:
    api_keys = list(db.execute(select(ApiKey).order_by(ApiKey.created_at.desc())).scalars())
    clients = list(db.execute(select(OAuthClient).order_by(OAuthClient.created_at.desc())).scalars())
    base_url = str(request.base_url).rstrip("/")
    ctx = {
        "request": request,
        "user": user,
        "active": "access",
        "api_keys": api_keys,
        "clients": clients,
        "token_url": f"{base_url}/oauth/token",
        "provision_url": f"{base_url}/api/v1/provision",
    }
    ctx.update(extra)
    return ctx


@router.get("/access", response_class=HTMLResponse)
def access_page(request: Request, user: AdminUser = Depends(require_login), db: Session = Depends(get_db)):
    return templates.TemplateResponse("access.html", _access_context(request, db, user))


@router.post("/access/api-keys")
def create_api_key(
    request: Request,
    name: str = Form(...),
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    full, prefix = security.new_api_key()
    db.add(ApiKey(name=name.strip() or "unnamed", prefix=prefix, key_hash=security.hash_secret(full)))
    db.commit()
    return templates.TemplateResponse(
        "access.html", _access_context(request, db, user, new_api_key=full)
    )


@router.post("/access/api-keys/{key_id}/revoke")
def revoke_api_key(key_id: int, user: AdminUser = Depends(require_login), db: Session = Depends(get_db)):
    key = db.get(ApiKey, key_id)
    if key is not None:
        key.revoked = True
        db.commit()
    return RedirectResponse("/access", status_code=303)


@router.post("/access/oauth-clients")
def create_oauth_client(
    request: Request,
    name: str = Form(...),
    user: AdminUser = Depends(require_login),
    db: Session = Depends(get_db),
):
    client_id = security.new_client_id()
    client_secret = security.new_client_secret()
    db.add(
        OAuthClient(
            name=name.strip() or "unnamed",
            client_id=client_id,
            client_secret_hash=security.hash_secret(client_secret),
        )
    )
    db.commit()
    return templates.TemplateResponse(
        "access.html",
        _access_context(request, db, user, new_client_id=client_id, new_client_secret=client_secret),
    )


@router.post("/access/oauth-clients/{client_id}/revoke")
def revoke_oauth_client(client_id: int, user: AdminUser = Depends(require_login), db: Session = Depends(get_db)):
    client = db.get(OAuthClient, client_id)
    if client is not None:
        client.revoked = True
        db.commit()
    return RedirectResponse("/access", status_code=303)
