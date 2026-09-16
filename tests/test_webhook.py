from fastapi.testclient import TestClient

from app.main import app
from app.models import Tenant

client = TestClient(app)


def _payload(phone_number_id, sender_wa, text):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": phone_number_id},
        "contacts": [{"wa_id": sender_wa, "profile": {"name": "\u05d1\u05d5\u05d3\u05e7"}}],
        "messages": [{"from": sender_wa, "id": "wamid.TEST", "type": "text",
                      "text": {"body": text}}]}}]}]}


def test_verify_ok():
    r = client.get("/webhook", params={"hub.mode": "subscribe",
                                       "hub.verify_token": "synappse-verify-token",
                                       "hub.challenge": "12345"})
    assert r.status_code == 200 and r.text == "12345"


def test_verify_wrong_token():
    r = client.get("/webhook", params={"hub.mode": "subscribe",
                                       "hub.verify_token": "nope",
                                       "hub.challenge": "12345"})
    assert r.status_code == 403


def test_inbound_message_flows():
    tenant = None
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter_by(slug="demo-plumber").first()
    finally:
        db.close()
    assert tenant is not None
    r = client.post("/webhook", json=_payload(tenant.phone_number_id, "972549990001",
                                              "\u05db\u05de\u05d4 \u05e2\u05d5\u05dc\u05d4 \u05d1\u05d9\u05e7\u05d5\u05e8 \u05d8\u05db\u05e0\u05d0\u05d9?"))
    assert r.status_code == 200


def test_dashboard_and_stats():
    r = client.get("/dashboard/demo-plumber")
    assert r.status_code == 200
    assert "\u05d3\u05d5\u05d3 \u05d0\u05d9\u05e0\u05e1\u05d8\u05dc\u05e6\u05d9\u05d4" in r.text
    r = client.get("/api/demo-plumber/stats")
    assert r.status_code == 200 and r.json()["tenant"] == "demo-plumber"


def test_admin_requires_token():
    assert client.get("/api/admin/tenants").status_code == 401
    r = client.get("/api/admin/tenants", headers={"X-Admin-Token": "dev-admin-token"})
    assert r.status_code == 200 and r.json()[0]["slug"] == "demo-plumber"
