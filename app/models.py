"""SQLAlchemy ORM models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Mailbox(Base):
    """A provisioned (mock) mailbox for an employee."""

    __tablename__ = "mailboxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Identity from the source HR system (Saviynt). Used for read-back / idempotency.
    external_employee_id: Mapped[str | None] = mapped_column(String(128), index=True, default=None)

    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    company: Mapped[str | None] = mapped_column(String(256), default=None)
    department: Mapped[str | None] = mapped_column(String(256), default=None)
    job_title: Mapped[str | None] = mapped_column(String(256), default=None)

    display_name: Mapped[str] = mapped_column(String(256))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    user_principal_name: Mapped[str] = mapped_column(String(320), index=True)

    status: Mapped[str] = mapped_column(String(32), default="active")  # active | disabled
    source: Mapped[str] = mapped_column(String(32), default="api")     # api | ui | webhook

    callback_status: Mapped[str] = mapped_column(String(32), default="none")  # none|pending|success|failed
    callback_detail: Mapped[str | None] = mapped_column(Text, default=None)

    raw_payload: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class DomainMapping(Base):
    """Maps a company value to the email domain new hires there should receive."""

    __tablename__ = "domain_mappings"
    __table_args__ = (UniqueConstraint("company", name="uq_domain_company"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company: Mapped[str] = mapped_column(String(256), index=True)
    domain: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Config(Base):
    """Singleton (id=1) of live, UI-editable configuration."""

    __tablename__ = "config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    email_format: Mapped[str] = mapped_column(String(32), default="first.last")
    email_custom_pattern: Mapped[str] = mapped_column(String(256), default="{f}{last}")
    default_domain: Mapped[str] = mapped_column(String(256), default="demo365.local")

    callback_enabled: Mapped[bool] = mapped_column(default=False)
    callback_url: Mapped[str] = mapped_column(String(512), default="")
    callback_method: Mapped[str] = mapped_column(String(8), default="POST")
    callback_auth_header_name: Mapped[str] = mapped_column(String(128), default="")
    callback_auth_header_value: Mapped[str] = mapped_column(String(512), default="")
    # JSON string mapping Saviynt field names -> tokens, e.g. {"email": "{email}", "id": "{external_employee_id}"}
    callback_body_template: Mapped[str] = mapped_column(
        Text, default='{"employeeId": "{external_employee_id}", "email": "{email}"}'
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class ActivityLog(Base):
    """Audit trail of provisioning + callback events, surfaced in the UI."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event: Mapped[str] = mapped_column(String(64))  # provision | callback | error
    level: Mapped[str] = mapped_column(String(16), default="info")  # info | warn | error
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class AdminUser(Base):
    """A human who can sign in to the web UI."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class UserSession(Base):
    """Server-side session; the cookie holds only the opaque token."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApiKey(Base):
    """A machine credential Saviynt sends as the X-API-Key header."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    prefix: Mapped[str] = mapped_column(String(32), index=True)  # non-secret, for display
    key_hash: Mapped[str] = mapped_column(String(256))
    revoked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class OAuthClient(Base):
    """An OAuth2 client-credentials app (client_id + hashed client_secret)."""

    __tablename__ = "oauth_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    client_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    client_secret_hash: Mapped[str] = mapped_column(String(256))
    revoked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class OAuthToken(Base):
    """A short-lived Bearer access token issued to an OAuth client."""

    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    client_pk: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
