import logging

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from . import whatsapp
from .config import settings
from .dashboard import router as dashboard_router
from .db import Base, engine as db_engine, get_db
from .engine import Engine
from .models import Tenant
from .seed_demo import seed_demo

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("synappse.main")

Base.metadata.create_all(db_engine)


def make_engine(db) -> Engine:
    return Engine(db)


@asynccontextmanager
async def lifespan(_app):
    db = next(get_db())
    try:
        if not db.query(Tenant).count():
            seed_demo(db)
            log.info("seeded demo tenant")
    finally:
        db.close()
    yield


app = FastAPI(title="SynAppse Agent", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/webhook", response_class=PlainTextResponse)
def webhook_verify(hub_mode: str = Query("", alias="hub.mode"),
                   hub_verify_token: str = Query("", alias="hub.verify_token"),
                   hub_challenge: str = Query("", alias="hub.challenge")):
    if hub_mode == "subscribe" and hub_verify_token == settings.verify_token:
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("forbidden", status_code=403)


@app.post("/webhook")
async def webhook_inbound(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    if not whatsapp.verify_signature(body, request.headers.get("X-Hub-Signature-256", "")):
        return Response(status_code=401)
    payload = await request.json()
    eng = make_engine(db)
    for msg in whatsapp.parse_payload(payload):
        tenant = db.query(Tenant).filter_by(phone_number_id=msg["phone_number_id"]).first()
        if not tenant:
            log.warning("no tenant for phone_number_id=%s", msg["phone_number_id"])
            continue
        result = eng.handle_inbound(tenant, msg["from"], msg["name"], msg["text"])
        log.info("inbound from %s -> %s", msg["from"], result)
    return {"status": "ok"}


app.include_router(dashboard_router)
