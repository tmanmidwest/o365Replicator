"""Create tables and seed the singleton Config row from environment defaults."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine
from .models import Config, DomainMapping


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _seed_config(db)
        _seed_example_domains(db)
        db.commit()


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
