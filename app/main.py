"""FastAPI application entrypoint for o365Replicator."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import __version__
from .routers import auth_ui, config_api, oauth, provision, ui
from .seed import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="o365Replicator",
    description=(
        "A mock Microsoft 365 email provisioning service for POC/demo use. "
        "Saviynt fires a new-hire webhook at `/api/v1/provision`; the service generates "
        "an email address, stores a mailbox record, returns it synchronously, and "
        "(optionally) writes it back to Saviynt."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.include_router(oauth.router)
app.include_router(provision.router)
app.include_router(config_api.router)
app.include_router(auth_ui.router)
app.include_router(ui.router)

_static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/healthz", tags=["ops"], include_in_schema=True)
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
