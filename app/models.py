import json
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .db import Base


class Tenant(Base):
    """One tenant = one paying small business."""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    business_name = Column(String(255), nullable=False)
    phone_number_id = Column(String(64), nullable=False, index=True)  # WA Cloud API phone_number_id
    owner_phone = Column(String(32), nullable=False)  # where hot leads / escalations go
    language = Column(String(8), default="he")
    knowledge_json = Column(Text, default="{}")       # services, prices, hours, area, faq[]
    qualification_json = Column(Text, default="[]")   # fields the agent tries to collect
    agent_paused = Column(Boolean, default=False)     # kill switch
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="tenant")

    @property
    def knowledge(self) -> dict:
        return json.loads(self.knowledge_json or "{}")

    @knowledge.setter
    def knowledge(self, value: dict):
        self.knowledge_json = json.dumps(value, ensure_ascii=False)


class Customer(Base):
    """An end customer messaging the business. Doubles as the lead record."""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    wa_id = Column(String(32), nullable=False, index=True)  # customer WhatsApp number
    name = Column(String(255), default="")
    # lead qualification fields
    service = Column(String(255), default="")
    budget = Column(String(64), default="")
    area = Column(String(255), default="")
    urgency = Column(String(32), default="")
    status = Column(String(32), default="new")  # new | qualified | hot | handed_off | closed
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    mode = Column(String(16), default="ai")  # ai | human  (human = owner took over)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="conversations")
    customer = relationship("Customer")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    direction = Column(String(8), nullable=False)  # in | out
    body = Column(Text, nullable=False)
    tier = Column(String(16), default="")       # cheap | strong (outbound only)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class UsageCounter(Base):
    """Per-tenant monthly WhatsApp message metering.

    Meta pricing change (Oct 1, 2026): service messages stop being
    unlimited-free - 1,000 free per phone number per month, then billed at
    the local utility/authentication rate; utility templates inside the open
    24h window become billable too. We count outbound messages per tenant per
    month so every client sees usage before it becomes a bill.
    """
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("tenant_id", "month", name="uq_usage_tenant_month"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    month = Column(String(7), nullable=False)  # UTC "YYYY-MM"
    service_messages = Column(Integer, default=0)   # non-template messages inside the window
    template_messages = Column(Integer, default=0)  # template sends (billable per-message)
