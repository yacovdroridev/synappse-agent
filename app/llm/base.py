import json
from dataclasses import dataclass, field


@dataclass
class AgentReply:
    reply: str
    confidence: float
    lead_updates: dict = field(default_factory=dict)  # service / budget / area / urgency
    wants_human: bool = False


def build_system_prompt(knowledge: dict) -> str:
    return (
        "You are the WhatsApp assistant of a small business. "
        "Answer the customer's message helpfully and concisely, in the same language "
        "they used (Hebrew or English). Use ONLY the business knowledge below - never "
        "invent prices, hours or policies. Never give medical, legal or financial advice. "
        "While answering, naturally collect lead details you don't have yet: service needed, "
        "budget, area, urgency - one question at a time, only when it fits the conversation.\n\n"
        "BUSINESS KNOWLEDGE (JSON):\n%s\n\n"
        "Respond with STRICT JSON only:\n"
        '{"reply": "<message to customer>", "confidence": <0..1 how sure you are the reply '
        'is correct from the knowledge>, "lead_updates": {"service": "", "budget": "", '
        '"area": "", "urgency": ""} (only keys you learned from THIS message, else empty), '
        '"wants_human": <true only if the customer explicitly asks for a human>}'
    ) % json.dumps(knowledge, ensure_ascii=False, indent=1)
