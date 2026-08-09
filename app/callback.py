"""Write-back callback to SavvyIt: pushes the generated email back to the HR system.

The callback is intentionally generic so it can target whatever endpoint SavvyIt
exposes. The body is a JSON template whose tokens are filled from the mailbox
record, and an optional single auth header is attached.
"""

import json
import logging

import httpx

from .models import Config, Mailbox

logger = logging.getLogger("o365replicator.callback")


def _fill_template(template: str, mailbox: Mailbox) -> str:
    tokens = {
        "external_employee_id": mailbox.external_employee_id or "",
        "email": mailbox.email,
        "user_principal_name": mailbox.user_principal_name,
        "display_name": mailbox.display_name,
        "first_name": mailbox.first_name,
        "last_name": mailbox.last_name,
        "company": mailbox.company or "",
    }
    out = template
    for key, val in tokens.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def send_callback(config: Config, mailbox: Mailbox) -> tuple[str, str]:
    """Attempt the write-back. Returns (status, detail) — never raises."""
    if not config.callback_enabled or not config.callback_url:
        return "none", "callback disabled or no URL configured"

    body_str = _fill_template(config.callback_body_template, mailbox)
    headers = {"Content-Type": "application/json"}
    if config.callback_auth_header_name and config.callback_auth_header_value:
        headers[config.callback_auth_header_name] = config.callback_auth_header_value

    # Validate the filled template is JSON so we send a clean body.
    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError as exc:
        detail = f"callback body template is not valid JSON after filling: {exc}"
        logger.warning(detail)
        return "failed", detail

    method = (config.callback_method or "POST").upper()
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.request(method, config.callback_url, json=payload, headers=headers)
        detail = f"{method} {config.callback_url} -> {resp.status_code}"
        if resp.is_success:
            logger.info("callback ok: %s", detail)
            return "success", detail
        logger.warning("callback non-2xx: %s | body=%s", detail, resp.text[:500])
        return "failed", f"{detail} | body={resp.text[:500]}"
    except httpx.HTTPError as exc:
        detail = f"callback request error: {exc}"
        logger.warning(detail)
        return "failed", detail
