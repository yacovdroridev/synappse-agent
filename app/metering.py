"""Per-tenant monthly message metering (Meta Oct 1, 2026 pricing change)."""
from datetime import datetime

from .models import UsageCounter

FREE_SERVICE_MESSAGES_PER_MONTH = 1000  # per phone number, resets monthly


def current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def record_outbound(db, tenant_id: int, category: str = "service") -> None:
    """Count one outbound WhatsApp message. category: service | template."""
    month = current_month()
    row = (db.query(UsageCounter)
           .filter_by(tenant_id=tenant_id, month=month).first())
    if not row:
        row = UsageCounter(tenant_id=tenant_id, month=month)
        db.add(row)
        db.flush()
    if category == "template":
        row.template_messages = (row.template_messages or 0) + 1
    else:
        row.service_messages = (row.service_messages or 0) + 1


def get_usage(db, tenant_id: int, month: str = "") -> dict:
    month = month or current_month()
    row = (db.query(UsageCounter)
           .filter_by(tenant_id=tenant_id, month=month).first())
    service = row.service_messages if row else 0
    return {
        "month": month,
        "service_messages": service,
        "template_messages": row.template_messages if row else 0,
        "free_allowance": FREE_SERVICE_MESSAGES_PER_MONTH,
        "billable_service_messages": max(0, service - FREE_SERVICE_MESSAGES_PER_MONTH),
    }
