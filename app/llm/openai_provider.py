import json
import logging

import httpx

from ..config import settings
from .base import AgentReply, build_system_prompt

log = logging.getLogger("synappse.llm.openai")


class OpenAIProvider:
    def answer(self, knowledge: dict, history: list, message: str, model: str) -> AgentReply:
        messages = [{"role": "system", "content": build_system_prompt(knowledge)}]
        for h in history:
            messages.append({"role": "user" if h["direction"] == "in" else "assistant",
                             "content": h["body"]})
        messages.append({"role": "user", "content": message})
        try:
            resp = httpx.post(
                "%s/chat/completions" % settings.openai_base_url.rstrip("/"),
                headers={"Authorization": "Bearer %s" % settings.openai_api_key},
                json={"model": model, "messages": messages, "temperature": 0.3,
                      "response_format": {"type": "json_object"}},
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            return AgentReply(
                reply=str(data.get("reply", "")).strip(),
                confidence=float(data.get("confidence", 0.5)),
                lead_updates={k: v for k, v in (data.get("lead_updates") or {}).items() if v},
                wants_human=bool(data.get("wants_human", False)),
            )
        except Exception as exc:  # API failure -> escalate to human, never guess
            log.warning("LLM call failed (%s): %s", model, exc)
            return AgentReply(
                reply="\u05e1\u05dc\u05d9\u05d7\u05d4, \u05d9\u05e9 \u05dc\u05d9 \u05ea\u05e7\u05dc\u05d4 \u05d6\u05de\u05e0\u05d9\u05ea - \u05d1\u05e2\u05dc \u05d4\u05e2\u05e1\u05e7 \u05d9\u05d7\u05d6\u05d5\u05e8 \u05d0\u05dc\u05d9\u05da \u05d1\u05d4\u05e7\u05d3\u05dd.",
                confidence=0.0, wants_human=True)
