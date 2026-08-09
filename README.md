# o365Replicator

A **mock Microsoft 365 email provisioning service** for POC / demo use.

When a new employee lands in your HR system (SavvyIt) without an email address —
because in the real world O365 assigns it — this app stands in for O365. SavvyIt
fires a webhook, o365Replicator generates an email address from the employee's
name, stores a mailbox record, returns the address **synchronously**, and
(optionally) **writes it back** to SavvyIt so it can flow onward through your HR
connectors.

```
SavvyIt  ──POST /api/v1/provision──▶  o365Replicator ──generates──▶  jane.doe@acme.com
   ▲                                        │
   └───────── write-back callback ──────────┘  (optional, configurable)
```

## Features

- **Provisioning webhook** — `POST /api/v1/provision` accepts a new hire and returns a full mailbox record with the generated email.
- **Configurable address formats** — `first.last`, `f.last`, `first.l`, `firstlast`, `flast`, `first_last`, or a custom token pattern. Names are lowercased, de-accented, and stripped of symbols.
- **Domain by company** — map each company to its own domain (`Acme → acme.com`), with a default fallback.
- **Collision handling** — duplicate addresses get a numeric suffix (`jane.doe2@…`).
- **Idempotent** — repeat calls with the same `external_employee_id` return the existing mailbox.
- **Write-back callback** — push the email back to SavvyIt via a fully configurable URL / method / auth header / JSON body template.
- **Web UI** — dashboard, manual "new hire" form with live preview, settings, and an activity log.
- **Read-back API** — `GET /api/v1/mailboxes/by-employee/{id}` for SavvyIt to poll.
- **Interactive API docs** — Swagger UI at `/docs`.

## Run it

### Docker Compose (recommended)

```bash
docker compose up --build
```

Then open <http://localhost:8080>. Data persists in the `o365_data` volume.

### Locally (Python 3.12)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=sqlite:///./o365replicator.db uvicorn app.main:app --reload --port 8080
```

## Integrating with SavvyIt

**1. Provision (SavvyIt → o365Replicator).** On a new hire, POST the employee:

```bash
curl -X POST http://localhost:8080/api/v1/provision \
  -H "Content-Type: application/json" \
  -d '{
        "first_name": "Jane",
        "last_name": "Doe",
        "company": "Acme",
        "job_title": "Analyst",
        "external_employee_id": "E-1001"
      }'
```

Response (`201`):

```json
{
  "id": 1,
  "external_employee_id": "E-1001",
  "display_name": "Jane Doe",
  "email": "jane.doe@acme.com",
  "user_principal_name": "jane.doe@acme.com",
  "status": "active",
  "callback_status": "none",
  "...": "..."
}
```

SavvyIt can use `email` straight from this response — no second call needed.

**2. Read-back (optional).** If SavvyIt prefers to poll:

```bash
curl http://localhost:8080/api/v1/mailboxes/by-employee/E-1001
```

**3. Write-back (optional).** Enable it under **Settings → Write-back**. Configure
the callback URL (SavvyIt's employee-update endpoint), method, one auth header,
and a JSON body template. Available tokens:
`{email}` `{external_employee_id}` `{user_principal_name}` `{display_name}`
`{first_name}` `{last_name}` `{company}`. After each provision, o365Replicator
fires this callback and records the result in the activity log.

## Configuration

Bootstrap defaults come from environment variables (see [`.env.example`](.env.example)),
but everything is editable live in the web UI and persisted in the database:

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLite (or any SQLAlchemy URL) | `sqlite:////data/o365replicator.db` |
| `DEFAULT_EMAIL_FORMAT` | Initial address format | `first.last` |
| `DEFAULT_DOMAIN` | Fallback domain | `demo365.local` |
| `API_KEY` | If set, require `X-API-Key` on `/api/v1/provision` | _(disabled)_ |

## API reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/provision` | Provision a mailbox for a new hire |
| `POST` | `/api/v1/preview` | Preview an address without saving |
| `GET` | `/api/v1/mailboxes` | List all mailboxes |
| `GET` | `/api/v1/mailboxes/{id}` | Get one mailbox |
| `GET` | `/api/v1/mailboxes/by-employee/{external_id}` | Read-back by SavvyIt id |
| `DELETE` | `/api/v1/mailboxes/{id}` | Delete a mailbox |
| `GET/PUT` | `/api/v1/config` | Read / update live config |
| `GET/POST/DELETE` | `/api/v1/domains` | Manage company→domain mappings |
| `GET` | `/healthz` | Health check |

Full interactive docs: <http://localhost:8080/docs>.
