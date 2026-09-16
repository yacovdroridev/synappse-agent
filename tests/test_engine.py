import uuid

from app.engine import Engine
from app.models import Conversation, Customer


def wa():
    return "9725" + uuid.uuid4().hex[:9]


def test_faq_answer_cheap_tier(db, tenant, sender, sent):
    eng = Engine(db, sender=sender)
    r = eng.handle_inbound(tenant, wa(), "\u05d9\u05d5\u05e1\u05d9", "\u05d9\u05e9 \u05d0\u05d7\u05e8\u05d9\u05d5\u05ea \u05e2\u05dc \u05d4\u05e2\u05d1\u05d5\u05d3\u05d4?")
    assert r["tier"] == "cheap"
    assert "\u05e9\u05e0\u05d4 \u05d0\u05d7\u05e8\u05d9\u05d5\u05ea" in r["reply"]
    assert sent[-1]["to"] != tenant.owner_phone


def test_price_question(db, tenant, sender):
    eng = Engine(db, sender=sender)
    r = eng.handle_inbound(tenant, wa(), "", "\u05db\u05de\u05d4 \u05e2\u05d5\u05dc\u05d4 \u05e4\u05ea\u05d9\u05d7\u05ea \u05e1\u05ea\u05d9\u05de\u05d4?")
    assert "350" in r["reply"]


def test_unknown_escalates_to_strong(db, tenant, sender):
    eng = Engine(db, sender=sender)
    r = eng.handle_inbound(tenant, wa(), "", "\u05de\u05d4 \u05d3\u05e2\u05ea\u05da \u05e2\u05dc \u05d4\u05de\u05e6\u05d1 \u05d1\u05e6\u05e4\u05d5\u05df?")
    assert r["tier"] == "strong"


def test_hot_lead_notifies_owner(db, tenant, sender, sent):
    eng = Engine(db, sender=sender)
    customer_wa = wa()
    r = eng.handle_inbound(tenant, customer_wa, "\u05de\u05e9\u05d4", "\u05d4\u05d9\u05d9, \u05d9\u05e9 \u05dc\u05d9 \u05e0\u05d6\u05d9\u05dc\u05d4 \u05d3\u05d7\u05d5\u05e4\u05d4!")
    assert r["customer_status"] == "hot"
    assert r["hot_notified"] is True
    owner_msgs = [m for m in sent if m["to"] == tenant.owner_phone]
    assert owner_msgs and "\u05dc\u05d9\u05d3 \u05d7\u05dd" in owner_msgs[-1]["text"]
    assert "\u05e0\u05d6\u05d9\u05dc\u05d4" in owner_msgs[-1]["text"]


def test_hot_lead_notified_only_once(db, tenant, sender, sent):
    eng = Engine(db, sender=sender)
    customer_wa = wa()
    eng.handle_inbound(tenant, customer_wa, "", "\u05e1\u05ea\u05d9\u05de\u05d4 \u05d3\u05d7\u05d5\u05e4\u05d4 \u05d1\u05db\u05d9\u05d5\u05e8")
    n = len([m for m in sent if m["to"] == tenant.owner_phone])
    eng.handle_inbound(tenant, customer_wa, "", "\u05d5\u05db\u05de\u05d4 \u05d6\u05d4 \u05d9\u05e2\u05dc\u05d4?")
    assert len([m for m in sent if m["to"] == tenant.owner_phone]) == n


def test_human_request_handoff(db, tenant, sender, sent):
    eng = Engine(db, sender=sender)
    customer_wa = wa()
    r = eng.handle_inbound(tenant, customer_wa, "", "\u05d0\u05e0\u05d9 \u05e8\u05d5\u05e6\u05d4 \u05dc\u05d3\u05d1\u05e8 \u05e2\u05dd \u05e0\u05e6\u05d9\u05d2")
    assert r["mode"] == "human"
    assert any("\u05d1\u05e7\u05e9\u05ea \u05e0\u05e6\u05d9\u05d2" in m["text"] for m in sent if m["to"] == tenant.owner_phone)
    # after handoff, no more auto-replies
    sent.clear()
    r2 = eng.handle_inbound(tenant, customer_wa, "", "\u05d4\u05dc\u05d5?")
    assert r2["skipped"] == "human_mode"
    assert sent == []


def test_kill_switch(db, tenant, sender, sent):
    tenant.agent_paused = True
    db.commit()
    try:
        eng = Engine(db, sender=sender)
        r = eng.handle_inbound(tenant, wa(), "", "\u05db\u05de\u05d4 \u05e2\u05d5\u05dc\u05d4 \u05d1\u05d9\u05e7\u05d5\u05e8?")
        assert r["skipped"] == "paused"
        assert sent == []
    finally:
        tenant.agent_paused = False
        db.commit()


def test_lead_fields_accumulate(db, tenant, sender):
    eng = Engine(db, sender=sender)
    customer_wa = wa()
    eng.handle_inbound(tenant, customer_wa, "\u05d3\u05e0\u05d9", "\u05e6\u05e8\u05d9\u05da \u05dc\u05ea\u05e7\u05df \u05d3\u05d5\u05d3")
    eng.handle_inbound(tenant, customer_wa, "", "\u05d4\u05ea\u05e7\u05e6\u05d9\u05d1 \u05e9\u05dc\u05d9 500 \u05e9\u05e7\u05dc")
    c = db.query(Customer).filter_by(wa_id=customer_wa).first()
    assert c.service == "\u05d3\u05d5\u05d3"
    assert "500" in c.budget
