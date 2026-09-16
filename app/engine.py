"""Conversation engine: two-tier LLM routing, lead qualification, handoff.

Flow per inbound message:
1. log it; skip auto-reply if tenant paused (kill switch) or conversation is
   in human mode.
2. cheap model answers; if confidence < threshold -> strong model re-answers.
3. apply lead updates; detect explicit human request -> handoff + owner alert.
4. send the reply; when a lead turns hot -> owner gets a WhatsApp summary.
"""
import logging
from datetime import datetime

from . import whatsapp
from .config import settings
from .llm import get_provider
from .models import Conversation, Customer, Message, Tenant

log = logging.getLogger("synappse.engine")

HOT_URGENCY = {"\u05d2\u05d1\u05d5\u05d4\u05d4", "high"}


def is_hot(customer: Customer) -> bool:
    if customer.service and (customer.urgency or "").lower() in HOT_URGENCY:
        return True
    if customer.service and customer.budget and customer.area:
        return True
    return False


def is_qualified(customer: Customer) -> bool:
    filled = sum(1 for f in (customer.service, customer.budget, customer.area, customer.urgency) if f)
    return bool(customer.service) and filled >= 2


def lead_summary(customer: Customer) -> str:
    return (
        "\U0001F525 \u05dc\u05d9\u05d3 \u05d7\u05dd!\n"
        "\u05e9\u05dd: %(name)s\n\u05d8\u05dc\u05e4\u05d5\u05df: %(wa_id)s\n"
        "\u05e9\u05d9\u05e8\u05d5\u05ea: %(service)s\n\u05d3\u05d7\u05d9\u05e4\u05d5\u05ea: %(urgency)s\n"
        "\u05ea\u05e7\u05e6\u05d9\u05d1: %(budget)s\n\u05d0\u05d6\u05d5\u05e8: %(area)s"
    ) % {
        "name": customer.name or "-", "wa_id": customer.wa_id,
        "service": customer.service or "-", "urgency": customer.urgency or "-",
        "budget": customer.budget or "-", "area": customer.area or "-",
    }


class Engine:
    def __init__(self, db, provider=None, sender=None):
        self.db = db
        self.provider = provider or get_provider()
        self.sender = sender or whatsapp.send_text

    def _get_or_create(self, tenant: Tenant, wa_id: str, name: str):
        customer = (self.db.query(Customer)
                    .filter_by(tenant_id=tenant.id, wa_id=wa_id).first())
        if not customer:
            customer = Customer(tenant_id=tenant.id, wa_id=wa_id, name=name or "")
            self.db.add(customer)
            self.db.flush()
        elif name and not customer.name:
            customer.name = name
        convo = (self.db.query(Conversation)
                 .filter_by(tenant_id=tenant.id, customer_id=customer.id)
                 .order_by(Conversation.id.desc()).first())
        if not convo:
            convo = Conversation(tenant_id=tenant.id, customer_id=customer.id)
            self.db.add(convo)
            self.db.flush()
        return customer, convo

    def handle_inbound(self, tenant: Tenant, wa_from: str, name: str, text: str) -> dict:
        customer, convo = self._get_or_create(tenant, wa_from, name)
        self.db.add(Message(conversation_id=convo.id, direction="in", body=text))
        self.db.flush()

        if tenant.agent_paused:
            self.db.commit()
            return {"skipped": "paused"}
        if convo.mode == "human":
            self.db.commit()
            return {"skipped": "human_mode"}

        history = [{"direction": m.direction, "body": m.body} for m in convo.messages[-10:]]

        reply = self.provider.answer(knowledge=tenant.knowledge, history=history,
                                     message=text, model=settings.cheap_model)
        tier = "cheap"
        if reply.confidence < settings.confidence_threshold and not reply.wants_human:
            reply = self.provider.answer(knowledge=tenant.knowledge, history=history,
                                         message=text, model=settings.strong_model)
            tier = "strong"

        for field_name in ("service", "budget", "area", "urgency"):
            value = reply.lead_updates.get(field_name)
            if value:
                setattr(customer, field_name, value)

        if reply.wants_human:
            convo.mode = "human"
            customer.status = "handed_off"
            self.sender(tenant.phone_number_id, tenant.owner_phone,
                        "\u05d1\u05e7\u05e9\u05ea \u05e0\u05e6\u05d9\u05d2: %s (%s) \u05de\u05d1\u05e7\u05e9 \u05dc\u05d3\u05d1\u05e8 \u05e2\u05dd \u05d1\u05df \u05d0\u05d3\u05dd. \u05d4\u05e9\u05d9\u05d7\u05d4 \u05d4\u05d5\u05e2\u05d1\u05e8\u05d4 \u05d0\u05dc\u05d9\u05da."
                        % (customer.name or "\u05dc\u05dc\u05d0 \u05e9\u05dd", customer.wa_id))

        was_hot = customer.status == "hot"
        if customer.status not in ("handed_off", "closed"):
            if is_hot(customer):
                customer.status = "hot"
            elif is_qualified(customer):
                customer.status = "qualified"

        self.sender(tenant.phone_number_id, wa_from, reply.reply)
        self.db.add(Message(conversation_id=convo.id, direction="out", body=reply.reply,
                            tier=tier, confidence=reply.confidence))

        newly_hot = customer.status == "hot" and not was_hot
        if newly_hot:
            self.sender(tenant.phone_number_id, tenant.owner_phone, lead_summary(customer))

        customer.updated_at = datetime.utcnow()
        self.db.commit()
        return {"reply": reply.reply, "tier": tier, "confidence": reply.confidence,
                "customer_status": customer.status, "mode": convo.mode,
                "hot_notified": newly_hot}
