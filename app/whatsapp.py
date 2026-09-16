"""WhatsApp Cloud API client + webhook parsing.

Works with Meta direct or a BSP (Twilio / 360dialog) that exposes the
Cloud API payload shape. When WHATSAPP_TOKEN is empty (or the tenant uses
a DEMO phone_number_id) outbound messages are logged, not sent - this is
what lets us demo the full flow before real credentials exist.
"""
import hashlib
import hmac
import logging

import httpx

from .config import settings

log = logging.getLogger("synappse.whatsapp")


def verify_signature(body: bytes, signature_header: str) -> bool:
    """Validate X-Hub-Signature-256. Skipped when no app secret configured."""
    if not settings.whatsapp_app_secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header[len("sha256="):])


def parse_payload(payload: dict) -> list:
    """Extract inbound text messages from a Cloud API webhook payload."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            names = {c.get("wa_id"): c.get("profile", {}).get("name", "")
                     for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                if m.get("type") != "text":
                    continue
                out.append({
                    "phone_number_id": phone_number_id,
                    "from": m.get("from", ""),
                    "name": names.get(m.get("from", ""), ""),
                    "text": m.get("text", {}).get("body", ""),
                    "message_id": m.get("id", ""),
                })
    return out


def send_text(phone_number_id: str, to: str, text: str) -> dict:
    """Send a text message. Dry-run (log only) when no token / demo number."""
    if not settings.whatsapp_token or str(phone_number_id).startswith("DEMO"):
        log.info("[DRY-RUN] whatsapp -> %s: %s", to, text)
        return {"dry_run": True, "to": to, "text": text}
    url = "https://graph.facebook.com/%s/%s/messages" % (settings.whatsapp_api_version, phone_number_id)
    resp = httpx.post(
        url,
        headers={"Authorization": "Bearer %s" % settings.whatsapp_token},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
