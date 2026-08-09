# o365Replicator

A **mock Microsoft 365 email provisioning service** for POC / demo use.

When a new employee lands in your HR system (Saviynt) without an email address —
because in the real world O365 assigns it — this app stands in for O365. Saviynt
fires a webhook, o365Replicator generates an email address from the employee's
name, stores a mailbox record, returns the address **synchronously**, and
(optionally) **writes it back** to Saviynt so it can flow onward through your HR
connectors.

```
Saviynt  ──POST /api/v1/provision──▶  o365Replicator ──generates──▶  jane.doe@acme.com
   ▲                                        │
   └───────── write-back callback ──────────┘  (optional, configurable)
```

## Features

- **Provisioning webhook** — `POST /api/v1/provision` accepts a new hire and returns a full mailbox record with the generated email.
- **Configurable address formats** — `first.last`, `f.last`, `first.l`, `firstlast`, `flast`, `first_last`, or a custom token pattern. Names are lowercased, de-accented, and stripped of symbols.
- **Domain by company** — map each company to its own domain (`Acme → acme.com`), with a default fallback.
- **Collision handling** — duplicate addresses get a numeric suffix (`jane.doe2@…`).
- **Idempotent** — repeat calls with the same `external_employee_id` return the existing mailbox.
- **Write-back callback** — push the email back to Saviynt via a fully configurable URL / method / auth header / JSON body template.
- **Authentication** — login-protected web UI (admin sessions) and machine auth for Saviynt via **API keys** *and* **OAuth2 client credentials**. Built for internet exposure over a Cloudflare tunnel.
- **Web UI** — dashboard, manual "new hire" form with live preview, settings, credentials manager, and an activity log.
- **Read-back API** — `GET /api/v1/mailboxes/by-employee/{id}` for Saviynt to poll.
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

## Authentication

The app is designed to sit behind a **Cloudflare tunnel** (which terminates HTTPS),
so both the UI and the API are protected.

### UI login

On first launch, if no admin exists the first visit shows a **one-time setup screen**
to create the admin account. Alternatively, bootstrap it from the environment:

```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<a strong password>
```

Passwords are stored only as PBKDF2 hashes. Sessions are server-side; the cookie is
HttpOnly / SameSite=Lax / Secure. **Keep `COOKIE_SECURE=true` in production** (set it
`false` only for local `http://` testing). Change your password anytime under **Account**.

### Machine credentials for Saviynt (Access page)

Under **Access & Credentials** you can mint either mechanism — pick whichever the
Saviynt REST connector is configured for. Secrets are shown **once** and stored hashed.

- **API key** — send as header `X-API-Key: <key>`.
- **OAuth2 client credentials** — `client_id` + `client_secret`, exchanged at the token
  endpoint for a short-lived Bearer token.

```bash
# OAuth2 client-credentials flow
curl -X POST https://<your-host>/oauth/token \
  -d 'grant_type=client_credentials&client_id=<id>&client_secret=<secret>'
# -> {"access_token":"…","token_type":"Bearer","expires_in":3600}

curl -X POST https://<your-host>/api/v1/provision \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" -d '{ "first_name": "...", "last_name": "..." }'
```

The token endpoint also accepts credentials via HTTP Basic auth. Both keys and clients
can be **revoked** from the UI at any time.

## Integrating with Saviynt

**1. Provision (Saviynt → o365Replicator).** On a new hire, POST the employee
(with an `X-API-Key` or `Authorization: Bearer` header — omitted below for brevity):

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

Saviynt can use `email` straight from this response — no second call needed.

**2. Read-back (optional).** If Saviynt prefers to poll:

```bash
curl http://localhost:8080/api/v1/mailboxes/by-employee/E-1001
```

**3. Write-back (optional).** Enable it under **Settings → Write-back**. Configure
the callback URL (Saviynt's employee-update endpoint), method, one auth header,
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
| `GET` | `/api/v1/mailboxes/by-employee/{external_id}` | Read-back by Saviynt id |
| `DELETE` | `/api/v1/mailboxes/{id}` | Delete a mailbox |
| `GET/PUT` | `/api/v1/config` | Read / update live config |
| `GET/POST/DELETE` | `/api/v1/domains` | Manage company→domain mappings |
| `GET` | `/healthz` | Health check |

### Interactive docs & Postman

FastAPI generates the docs automatically:

| URL | What |
|---|---|
| `/docs` | Swagger UI — interactive, "Try it out" |
| `/redoc` | ReDoc — clean reference format |
| `/openapi.json` | Raw OpenAPI 3.1 spec |

A snapshot of the spec is committed at [`docs/openapi.json`](docs/openapi.json).

**Import into Postman:** *Import → Link* and paste `https://<your-host>/openapi.json`
(or import the committed `docs/openapi.json` file). Postman generates a collection
covering every endpoint. Then set auth for the requests — either an `X-API-Key`
header, or configure **OAuth 2.0 (Client Credentials)** in Postman's *Authorization*
tab pointing at `https://<your-host>/oauth/token`.

> Note: `/docs`, `/redoc`, and `/openapi.json` are readable without logging in (the
> schema isn't secret, but the endpoints themselves still require auth). If you'd
> rather not expose them publicly, they can be disabled or gated — ask and I'll wire it.
