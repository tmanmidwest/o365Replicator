"""Server-rendered web UI for managing the mock provisioner."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ActivityLog, DomainMapping, Mailbox
from ..schemas import ConfigIn, EmployeeIn
from ..seed import get_config
from ..services import provision_employee

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    mailboxes = list(db.execute(select(Mailbox).order_by(Mailbox.created_at.desc())).scalars())
    config = get_config(db)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "mailboxes": mailboxes, "config": config, "active": "dashboard"},
    )


@router.get("/new", response_class=HTMLResponse)
def new_form(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        "new.html", {"request": request, "config": get_config(db), "active": "new"}
    )


@router.post("/new")
def create_mailbox(
    first_name: str = Form(...),
    last_name: str = Form(...),
    company: str = Form(""),
    department: str = Form(""),
    job_title: str = Form(""),
    external_employee_id: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    employee = EmployeeIn(
        first_name=first_name,
        last_name=last_name,
        company=company or None,
        department=department or None,
        job_title=job_title or None,
        external_employee_id=external_employee_id or None,
    )
    provision_employee(db, employee, source="ui")
    return RedirectResponse(url="/", status_code=303)


@router.post("/mailboxes/{mailbox_id}/delete")
def delete_mailbox_ui(mailbox_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is not None:
        db.delete(mailbox)
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    config = get_config(db)
    domains = list(db.execute(select(DomainMapping).order_by(DomainMapping.company)).scalars())
    from ..email_generator import FORMATS

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "config": config,
            "domains": domains,
            "formats": list(FORMATS.keys()),
            "active": "settings",
        },
    )


@router.post("/settings")
def save_settings(
    email_format: str = Form(...),
    email_custom_pattern: str = Form("{f}{last}"),
    default_domain: str = Form(...),
    callback_enabled: str = Form(""),
    callback_url: str = Form(""),
    callback_method: str = Form("POST"),
    callback_auth_header_name: str = Form(""),
    callback_auth_header_value: str = Form(""),
    callback_body_template: str = Form('{"employeeId": "{external_employee_id}", "email": "{email}"}'),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    config = get_config(db)
    payload = ConfigIn(
        email_format=email_format,
        email_custom_pattern=email_custom_pattern,
        default_domain=default_domain,
        callback_enabled=callback_enabled == "on",
        callback_url=callback_url,
        callback_method=callback_method,
        callback_auth_header_name=callback_auth_header_name,
        callback_auth_header_value=callback_auth_header_value,
        callback_body_template=callback_body_template,
    )
    for key, val in payload.model_dump().items():
        setattr(config, key, val)
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/domains")
def add_domain_ui(
    company: str = Form(...), domain: str = Form(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    existing = db.execute(
        select(DomainMapping).where(DomainMapping.company == company)
    ).scalar_one_or_none()
    if existing is not None:
        existing.domain = domain
    else:
        db.add(DomainMapping(company=company, domain=domain))
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/domains/{mapping_id}/delete")
def delete_domain_ui(mapping_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    mapping = db.get(DomainMapping, mapping_id)
    if mapping is not None:
        db.delete(mapping)
        db.commit()
    return RedirectResponse(url="/settings", status_code=303)


@router.get("/activity", response_class=HTMLResponse)
def activity_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    logs = list(
        db.execute(select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(200)).scalars()
    )
    return templates.TemplateResponse(
        "activity.html", {"request": request, "logs": logs, "active": "activity"}
    )
