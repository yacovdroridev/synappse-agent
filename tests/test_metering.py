import uuid

from app import metering
from app.engine import Engine
from app.models import UsageCounter


def wa():
    return "9725" + uuid.uuid4().hex[:9]


def test_reply_is_metered_as_service(db, tenant, sender):
    eng = Engine(db, sender=sender)
    eng.handle_inbound(tenant, wa(), "", "\u05db\u05de\u05d4 \u05e2\u05d5\u05dc\u05d4 \u05d1\u05d9\u05e7\u05d5\u05e8?")
    u = metering.get_usage(db, tenant.id)
    assert u["service_messages"] >= 1
    assert u["month"] == metering.current_month()
    assert u["free_allowance"] == 1000
    assert u["billable_service_messages"] == max(0, u["service_messages"] - 1000)


def test_owner_notifications_are_metered(db, tenant, sender):
    before = metering.get_usage(db, tenant.id)["service_messages"]
    eng = Engine(db, sender=sender)
    eng.handle_inbound(tenant, wa(), "", "\u05e0\u05d6\u05d9\u05dc\u05d4 \u05d3\u05d7\u05d5\u05e4\u05d4!")
    after = metering.get_usage(db, tenant.id)["service_messages"]
    # customer reply + owner hot-lead notification
    assert after - before == 2


def test_template_category(db, tenant):
    metering.record_outbound(db, tenant.id, "template")
    u = metering.get_usage(db, tenant.id)
    assert u["template_messages"] >= 1


def test_billable_math(db, tenant):
    month = metering.current_month()
    row = db.query(UsageCounter).filter_by(tenant_id=tenant.id, month=month).first()
    row.service_messages = 1001
    db.commit()
    u = metering.get_usage(db, tenant.id)
    assert u["billable_service_messages"] == 1


def test_stats_api_exposes_usage(db, tenant):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.get("/api/demo-plumber/stats")
    assert r.status_code == 200
    usage = r.json()["usage"]
    assert usage["free_allowance"] == 1000
    assert "service_messages" in usage and "month" in usage


def test_dashboard_shows_metering(db, tenant):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.get("/dashboard/demo-plumber")
    assert r.status_code == 200
    assert "1,000" in r.text
    assert "\u05d4\u05d5\u05d3\u05e2\u05d5\u05ea \u05e9\u05d9\u05e8\u05d5\u05ea" in r.text
