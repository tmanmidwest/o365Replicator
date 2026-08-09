"""Provisioning webhook + mailbox read API — the surface SavvyIt integrates against."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import email_generator
from ..database import get_db
from ..deps import require_api_key
from ..models import Mailbox
from ..schemas import EmployeeIn, MailboxOut, PreviewIn, PreviewOut
from ..seed import get_config
from ..services import provision_employee

router = APIRouter(prefix="/api/v1", tags=["provisioning"])


@router.post(
    "/provision",
    response_model=MailboxOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
    summary="Provision a mailbox for a new hire (SavvyIt onboarding webhook)",
)
def provision(employee: EmployeeIn, db: Session = Depends(get_db)) -> Mailbox:
    """Generate and store an email address for an employee, returning it synchronously.

    If write-back is enabled in settings, the app also pushes the email to SavvyIt.
    Idempotent on `external_employee_id`.
    """
    return provision_employee(db, employee, source="webhook")


@router.post("/preview", response_model=PreviewOut, summary="Preview an address without saving")
def preview(data: PreviewIn, db: Session = Depends(get_db)) -> PreviewOut:
    config = get_config(db)
    generated = email_generator.generate(
        db,
        config,
        first_name=data.first_name,
        last_name=data.last_name,
        company=data.company,
        department=data.department,
        ensure_unique=False,
    )
    return PreviewOut(
        email=generated.email,
        display_name=generated.display_name,
        domain=generated.domain,
        format_used=generated.format_used,
    )


@router.get("/mailboxes", response_model=list[MailboxOut], summary="List provisioned mailboxes")
def list_mailboxes(db: Session = Depends(get_db)) -> list[Mailbox]:
    return list(db.execute(select(Mailbox).order_by(Mailbox.created_at.desc())).scalars())


@router.get("/mailboxes/{mailbox_id}", response_model=MailboxOut)
def get_mailbox(mailbox_id: int, db: Session = Depends(get_db)) -> Mailbox:
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return mailbox


@router.get(
    "/mailboxes/by-employee/{external_employee_id}",
    response_model=MailboxOut,
    summary="Read back a mailbox by SavvyIt employee id",
)
def get_by_employee(external_employee_id: str, db: Session = Depends(get_db)) -> Mailbox:
    """The read-back endpoint SavvyIt can poll to retrieve the generated email."""
    mailbox = db.execute(
        select(Mailbox).where(Mailbox.external_employee_id == external_employee_id)
    ).scalar_one_or_none()
    if mailbox is None:
        raise HTTPException(status_code=404, detail="No mailbox for that employee id")
    return mailbox


@router.delete("/mailboxes/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mailbox(mailbox_id: int, db: Session = Depends(get_db)) -> None:
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    db.delete(mailbox)
    db.commit()
