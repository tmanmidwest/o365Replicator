"""Create tables and seed the singleton Config row from environment defaults."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import security
from .config import settings
from .database import Base, SessionLocal, engine
from .models import AdminUser, Config, DomainMapping

logger = logging.getLogger("o365replicator.seed")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _seed_config(db)
        _seed_example_domains(db)
        _seed_admin(db)
        db.commit()


def _seed_admin(db: Session) -> None:
    """Create the bootstrap admin from env vars if configured and none exists yet."""
    if db.execute(select(AdminUser.id).limit(1)).first() is not None:
        return
    if settings.admin_username and settings.admin_password:
        db.add(
            AdminUser(
                username=settings.admin_username.strip(),
                password_hash=security.hash_secret(settings.admin_password),
            )
        )
        logger.info("Seeded bootstrap admin '%s' from environment.", settings.admin_username)
    else:
        logger.info("No admin configured; first UI visit will show the setup screen.")


def _seed_config(db: Session) -> None:
    config = db.get(Config, 1)
    if config is not None:
        return
    db.add(
        Config(
            id=1,
            email_format=settings.default_email_format,
            email_custom_pattern=settings.default_email_custom_pattern,
            default_domain=settings.default_domain,
            callback_enabled=settings.callback_enabled,
            callback_url=settings.callback_url,
            callback_method=settings.callback_method,
            callback_auth_header_name=settings.callback_auth_header_name,
            callback_auth_header_value=settings.callback_auth_header_value,
        )
    )


def _seed_example_domains(db: Session) -> None:
    # Only seed examples if there are none, so we never clobber user edits.
    existing = db.execute(select(DomainMapping)).first()
    if existing is not None:
        return
    db.add_all(
        [
            DomainMapping(company="Acme", domain="acme.com"),
            DomainMapping(company="Globex", domain="globex.io"),
        ]
    )


def get_config(db: Session) -> Config:
    """Fetch the singleton config, creating it lazily if somehow missing."""
    config = db.get(Config, 1)
    if config is None:
        config = Config(id=1)
        db.add(config)
        db.commit()
    return config
