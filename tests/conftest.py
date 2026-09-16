import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["LLM_PROVIDER"] = "mock"
os.environ["WHATSAPP_TOKEN"] = ""

import pytest

from app.db import Base, SessionLocal, engine as db_engine
from app.models import Tenant
from app.seed_demo import seed_demo

Base.metadata.create_all(db_engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def tenant(db):
    t = db.query(Tenant).filter_by(slug="demo-plumber").first()
    if not t:
        t = seed_demo(db)
    return t


@pytest.fixture()
def sent():
    return []


@pytest.fixture()
def sender(sent):
    def _send(phone_number_id, to, text):
        sent.append({"phone_number_id": phone_number_id, "to": to, "text": text})
        return {"captured": True}
    return _send
