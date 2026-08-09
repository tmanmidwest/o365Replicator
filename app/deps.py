"""Shared FastAPI dependencies."""

from fastapi import Header, HTTPException, status

from .config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Enforce the API key on inbound provisioning calls, if one is configured.

    POC-friendly: when API_KEY is blank, auth is disabled entirely.
    """
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header.",
        )
