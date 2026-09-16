"""Deterministic rule-based provider: dev, demo and tests without LLM keys.

Mimics the two-tier behavior: the 'cheap' tier is confident on FAQ/hours/price
hits and unsure otherwise; the 'strong' tier handles the rest more gracefully.
"""
import re

from .base import AgentReply

HE_RE = re.compile(r"[\u0590-\u05FF]")
BUDGET_RE = re.compile(r"(\d[\d,]*)\s*(?:\u05e9\"\u05d7|\u05e9\u05e7\u05dc|\u20aa|\$|\u05d3\u05d5\u05dc\u05e8)")

HOURS_WORDS = ["\u05e9\u05e2\u05d5\u05ea", "\u05e4\u05ea\u05d5\u05d7", "\u05e1\u05d2\u05d5\u05e8", "\u05de\u05ea\u05d9 \u05d0\u05ea\u05dd", "hours", "open", "close"]
PRICE_WORDS = ["\u05de\u05d7\u05d9\u05e8", "\u05db\u05de\u05d4 \u05e2\u05d5\u05dc\u05d4", "\u05e2\u05dc\u05d5\u05ea", "\u05d4\u05e6\u05e2\u05ea \u05de\u05d7\u05d9\u05e8", "price", "cost", "how much", "quote"]
URGENCY_WORDS = ["\u05d3\u05d7\u05d5\u05e3", "\u05d3\u05d7\u05d5\u05e4\u05d4", "\u05e2\u05db\u05e9\u05d9\u05d5", "\u05de\u05d9\u05d9\u05d3\u05d9", "\u05d7\u05d9\u05e8\u05d5\u05dd", "\u05d4\u05d9\u05d5\u05dd", "urgent", "emergency", "asap", "now", "today"]
HUMAN_WORDS = ["\u05e0\u05e6\u05d9\u05d2", "\u05d1\u05df \u05d0\u05d3\u05dd", "\u05d0\u05d3\u05dd \u05d0\u05de\u05d9\u05ea\u05d9", "\u05d8\u05dc\u05e4\u05d5\u05df", "human", "representative", "real person", "call me"]


def _is_hebrew(text: str) -> bool:
    return bool(HE_RE.search(text))


class MockProvider:
    def answer(self, knowledge: dict, history: list, message: str, model: str) -> AgentReply:
        text = message.lower()
        he = _is_hebrew(message)
        updates = {}

        if any(w in text for w in HUMAN_WORDS):
            reply = ("\u05d1\u05e9\u05de\u05d7\u05d4, \u05de\u05e2\u05d1\u05d9\u05e8 \u05d0\u05ea\u05da \u05dc\u05d1\u05e2\u05dc \u05d4\u05e2\u05e1\u05e7 - \u05d4\u05d5\u05d0 \u05d9\u05d7\u05d6\u05d5\u05e8 \u05d0\u05dc\u05d9\u05da \u05d1\u05d4\u05e7\u05d3\u05dd. "
                     if he else "Sure, handing you over to the business owner - they'll get back to you shortly.")
            return AgentReply(reply=reply, confidence=0.95, wants_human=True)

        # service detection from knowledge
        for svc in knowledge.get("services", []):
            name = svc.get("name", "") if isinstance(svc, dict) else str(svc)
            if name and name.lower() in text:
                updates["service"] = name
                break
        if any(w in text for w in URGENCY_WORDS):
            updates["urgency"] = "\u05d2\u05d1\u05d5\u05d4\u05d4" if he else "high"
        m = BUDGET_RE.search(message)
        if m:
            updates["budget"] = m.group(0)

        # FAQ hit
        for item in knowledge.get("faq", []):
            q = item.get("q", "")
            key_words = [w for w in re.split(r"\s+", q) if len(w) > 3]
            if key_words and any(w.lower() in text for w in key_words):
                return AgentReply(reply=item.get("a", ""), confidence=0.9, lead_updates=updates)

        if any(w in text for w in HOURS_WORDS) and knowledge.get("hours"):
            return AgentReply(reply=str(knowledge["hours"]), confidence=0.85, lead_updates=updates)

        if any(w in text for w in PRICE_WORDS) and knowledge.get("prices"):
            lines = ["%s: %s" % (p.get("item", ""), p.get("price", "")) for p in knowledge["prices"]]
            prefix = "\u05d4\u05de\u05d7\u05d9\u05e8\u05d5\u05df \u05e9\u05dc\u05e0\u05d5:" if he else "Our price list:"
            return AgentReply(reply=prefix + "\n" + "\n".join(lines), confidence=0.8, lead_updates=updates)

        if updates.get("service"):
            reply = ("\u05e7\u05d9\u05d1\u05dc\u05ea\u05d9, %s. \u05db\u05de\u05d4 \u05d3\u05d7\u05d5\u05e3 \u05dc\u05da? \u05d5\u05d1\u05d0\u05d9\u05d6\u05d5 \u05d0\u05d6\u05d5\u05e8 \u05d0\u05ea/\u05d4?" % updates["service"]
                     if he else "Got it - %s. How urgent is it, and which area are you in?" % updates["service"])
            return AgentReply(reply=reply, confidence=0.75, lead_updates=updates)

        # unknown: cheap tier is unsure, strong tier handles gracefully
        if "mini" in model or "cheap" in model:
            reply = "\u05e8\u05d2\u05e2, \u05d0\u05e0\u05d9 \u05d1\u05d5\u05d3\u05e7..." if he else "One moment, let me check..."
            return AgentReply(reply=reply, confidence=0.3, lead_updates=updates)
        reply = ("\u05e9\u05d0\u05dc\u05d4 \u05d8\u05d5\u05d1\u05d4! \u05d0\u05e0\u05d9 \u05d0\u05d5\u05db\u05dc \u05dc\u05e2\u05d6\u05d5\u05e8 \u05d1\u05db\u05dc \u05e9\u05d0\u05dc\u05d4 \u05e2\u05dc \u05d4\u05e9\u05d9\u05e8\u05d5\u05ea\u05d9\u05dd, \u05d4\u05de\u05d7\u05d9\u05e8\u05d5\u05df \u05d5\u05e9\u05e2\u05d5\u05ea \u05d4\u05e4\u05e2\u05d9\u05dc\u05d5\u05ea \u05e9\u05dc\u05e0\u05d5. \u05d1\u05de\u05d4 \u05d0\u05d5\u05db\u05dc \u05dc\u05e2\u05d6\u05d5\u05e8?"
                 if he else "Good question! I can help with anything about our services, prices and hours. What do you need?")
        return AgentReply(reply=reply, confidence=0.7, lead_updates=updates)
