"""Provisioning service layer shared by the API and the web UI."""

import json

from sqlalchemy.orm import Session

from . import email_generator
from .callback import send_callback
from .models import ActivityLog, Config, Mailbox
from .schemas import EmployeeIn
from .seed import get_config


def log_activity(db: Session, event: str, message: str, *, level: str = "info", detail: str | None = None) -> None:
    db.add(ActivityLog(event=event, level=level, message=message, detail=detail))


def provision_employee(db: Session, employee: EmployeeIn, *, source: str = "api", run_callback: bool = True) -> Mailbox:
    """Generate a mailbox for an employee, persist it, and optionally write back to Saviynt.

    Idempotent on external_employee_id: if a mailbox already exists for that id,
    it is returned unchanged rather than creating a duplicate.
    """
    config: Config = get_config(db)

    if employee.external_employee_id:
        existing = (
            db.query(Mailbox)
            .filter(Mailbox.external_employee_id == employee.external_employee_id)
            .one_or_none()
        )
        if existing is not None:
            log_activity(
                db,
                "provision",
                f"Existing mailbox returned for employee {employee.external_employee_id}: {existing.email}",
            )
            db.commit()
            return existing

    generated = email_generator.generate(
        db,
        config,
        first_name=employee.first_name,
        last_name=employee.last_name,
        company=employee.company,
        department=employee.department,
    )

    mailbox = Mailbox(
        external_employee_id=employee.external_employee_id,
        first_name=employee.first_name,
        last_name=employee.last_name,
        company=employee.company,
        department=employee.department,
        job_title=employee.job_title,
        display_name=generated.display_name,
        email=generated.email,
        user_principal_name=generated.user_principal_name,
        source=source,
        raw_payload=json.dumps(employee.model_dump()),
    )
    db.add(mailbox)
    db.flush()  # assign PK before we log/callback

    log_activity(
        db,
        "provision",
        f"Provisioned {generated.email} for {generated.display_name}"
        + (f" (company={employee.company})" if employee.company else ""),
    )

    if run_callback and config.callback_enabled:
        mailbox.callback_status = "pending"
        status_result, detail = send_callback(config, mailbox)
        mailbox.callback_status = status_result
        mailbox.callback_detail = detail
        log_activity(
            db,
            "callback",
            f"Write-back to Saviynt for {generated.email}: {status_result}",
            level="info" if status_result in ("success", "none") else "warn",
            detail=detail,
        )

    db.commit()
    db.refresh(mailbox)
    return mailbox
