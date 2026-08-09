"""Pydantic request/response models for the API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmployeeIn(BaseModel):
    """Inbound new-hire payload from Saviynt (or the manual UI form)."""

    first_name: str = Field(..., min_length=1, examples=["Jane"])
    last_name: str = Field(..., min_length=1, examples=["Doe"])
    company: str | None = Field(default=None, examples=["Acme"])
    department: str | None = Field(default=None, examples=["Finance"])
    job_title: str | None = Field(default=None, examples=["Analyst"])
    external_employee_id: str | None = Field(
        default=None, description="Saviynt's employee id, used for read-back.", examples=["E-1001"]
    )


class MailboxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_employee_id: str | None
    first_name: str
    last_name: str
    company: str | None
    department: str | None
    job_title: str | None
    display_name: str
    email: str
    user_principal_name: str
    status: str
    source: str
    callback_status: str
    callback_detail: str | None
    created_at: datetime
    updated_at: datetime


class PreviewIn(BaseModel):
    first_name: str
    last_name: str
    company: str | None = None
    department: str | None = None


class PreviewOut(BaseModel):
    email: str
    display_name: str
    domain: str
    format_used: str


class DomainMappingIn(BaseModel):
    company: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)


class DomainMappingOut(DomainMappingIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ConfigIn(BaseModel):
    email_format: str
    email_custom_pattern: str = "{f}{last}"
    default_domain: str
    callback_enabled: bool = False
    callback_url: str = ""
    callback_method: str = "POST"
    callback_auth_header_name: str = ""
    callback_auth_header_value: str = ""
    callback_body_template: str = '{"employeeId": "{external_employee_id}", "email": "{email}"}'


class ConfigOut(ConfigIn):
    model_config = ConfigDict(from_attributes=True)
