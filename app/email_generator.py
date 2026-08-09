"""Email address generation: formatting, sanitizing, domain selection, collisions."""

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Config, DomainMapping, Mailbox

# Named local-part formats. Each maps to a token pattern resolved by _render().
FORMATS: dict[str, str] = {
    "first.last": "{first}.{last}",
    "f.last": "{f}.{last}",
    "first.l": "{first}.{l}",
    "firstlast": "{first}{last}",
    "flast": "{f}{last}",
    "first_last": "{first}_{last}",
    "custom": "",  # resolved from Config.email_custom_pattern
}


def slugify(value: str) -> str:
    """Lowercase, strip accents, and remove anything but [a-z0-9] from a name part."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_only.lower())


@dataclass
class GeneratedEmail:
    local_part: str
    domain: str
    email: str
    user_principal_name: str
    display_name: str
    format_used: str


def _render(pattern: str, first: str, last: str, company: str, department: str) -> str:
    """Resolve a token pattern into a sanitized local part."""
    f = slugify(first)
    ls = slugify(last)
    tokens = {
        "first": f,
        "last": ls,
        "f": f[:1],
        "l": ls[:1],
        "company": slugify(company),
        "department": slugify(department),
    }
    out = pattern
    for key, val in tokens.items():
        out = out.replace("{" + key + "}", val)
    # Collapse any leftover separators produced by empty tokens.
    out = re.sub(r"[._]{2,}", ".", out).strip("._")
    return out or "user"


def resolve_domain(db: Session, company: str | None, default_domain: str) -> str:
    """Pick the domain for a company via mappings, falling back to the default."""
    if company:
        stmt = select(DomainMapping).where(func.lower(DomainMapping.company) == company.strip().lower())
        mapping = db.execute(stmt).scalar_one_or_none()
        if mapping:
            return mapping.domain
    return default_domain


def _make_unique(db: Session, local_part: str, domain: str) -> str:
    """Append a counter until the full email address is unique in the DB."""
    candidate = f"{local_part}@{domain}"
    if db.execute(select(Mailbox).where(Mailbox.email == candidate)).scalar_one_or_none() is None:
        return candidate
    n = 2
    while True:
        candidate = f"{local_part}{n}@{domain}"
        if db.execute(select(Mailbox).where(Mailbox.email == candidate)).scalar_one_or_none() is None:
            return candidate
        n += 1


def generate(
    db: Session,
    config: Config,
    *,
    first_name: str,
    last_name: str,
    company: str | None = None,
    department: str | None = None,
    ensure_unique: bool = True,
) -> GeneratedEmail:
    """Produce a full, collision-safe email address for an employee."""
    fmt = config.email_format if config.email_format in FORMATS else "first.last"
    pattern = config.email_custom_pattern if fmt == "custom" else FORMATS[fmt]

    local_part = _render(pattern, first_name, last_name, company or "", department or "")
    domain = resolve_domain(db, company, config.default_domain)

    if ensure_unique:
        email = _make_unique(db, local_part, domain)
    else:
        email = f"{local_part}@{domain}"

    display_name = f"{first_name.strip()} {last_name.strip()}".strip()
    return GeneratedEmail(
        local_part=local_part,
        domain=domain,
        email=email,
        user_principal_name=email,  # UPN mirrors the primary SMTP address in this mock
        display_name=display_name,
        format_used=fmt,
    )
