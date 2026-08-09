"""OAuth2 client-credentials token endpoint for Saviynt's connector."""

import base64
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..auth import now_utc
from ..config import settings
from ..database import get_db
from ..models import OAuthClient, OAuthToken

router = APIRouter(tags=["oauth"])


def _client_from_basic(authorization: str | None) -> tuple[str, str] | None:
    if not authorization or not authorization.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(authorization[6:].strip()).decode("utf-8")
        client_id, client_secret = decoded.split(":", 1)
        return client_id, client_secret
    except (ValueError, UnicodeDecodeError):
        return None


@router.post("/oauth/token", summary="OAuth2 client-credentials token endpoint")
def issue_token(
    grant_type: str = Form(default="client_credentials"),
    client_id: str | None = Form(default=None),
    client_secret: str | None = Form(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Exchange client_id/client_secret for a short-lived Bearer access token.

    Credentials may be sent as form fields or via HTTP Basic auth, matching what
    Saviynt's REST connector supports.
    """
    if grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "unsupported_grant_type"},
        )

    basic = _client_from_basic(authorization)
    if basic is not None:
        client_id, client_secret = basic

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "invalid_request"}
        )

    client = db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id, OAuthClient.revoked.is_(False)
        )
    ).scalar_one_or_none()

    if client is None or not security.verify_secret(client_secret, client.client_secret_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_client"},
            headers={"WWW-Authenticate": "Basic"},
        )

    access_token = security.new_oauth_access_token()
    ttl = settings.oauth_token_ttl_seconds
    db.add(
        OAuthToken(
            token=access_token,
            client_pk=client.id,
            expires_at=now_utc() + timedelta(seconds=ttl),
        )
    )
    client.last_used_at = now_utc()
    db.commit()

    return {"access_token": access_token, "token_type": "Bearer", "expires_in": ttl}
