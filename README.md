# SynAppse Agent — סוכן AI אישי לעסקים קטנים ב-WhatsApp

Multi-tenant WhatsApp AI agent for small businesses (MVP per the approved spec).
One server, one tenant per client business: answers customers 24/7 in Hebrew/English
from a per-client knowledge base, qualifies leads (service / budget / area / urgency),
hands hot leads to the owner with a WhatsApp summary, escalates to a human on request,
and shows a basic dashboard.

## Stack

- Python 3.10+, FastAPI, SQLAlchemy (SQLite by default, Postgres-ready via `DATABASE_URL`)
- WhatsApp Business **Cloud API** (Meta direct or a BSP — Twilio / 360dialog)
- Two-tier LLM routing: cheap model answers ~80% of conversations; low-confidence
  answers escalate to a strong model (`CONFIDENCE_THRESHOLD`)
- **Mock LLM provider** built in: with no `OPENAI_API_KEY` the whole system runs
  deterministically — dev, demos and CI need zero credentials

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env        # works out of the box with no keys (mock LLM, dry-run WhatsApp)
uvicorn app.main:app --reload
```

The demo tenant seeds automatically on first run (decision #8: one permanent demo
setup — a plumber, the approved first niche). Try it:

```bash
# simulate an inbound WhatsApp message
curl -X POST localhost:8000/webhook -H 'Content-Type: application/json' -d '{
  "entry":[{"changes":[{"value":{
    "metadata":{"phone_number_id":"DEMO_PHONE_NUMBER_ID"},
    "contacts":[{"wa_id":"972549111222","profile":{"name":"בודק"}}],
    "messages":[{"from":"972549111222","id":"wamid.1","type":"text",
                 "text":{"body":"היי יש לי נזילה דחופה!"}}]}}]}]}'

# dashboard
open http://localhost:8000/dashboard/demo-plumber
```

Outbound WhatsApp messages are **dry-run (logged)** until `WHATSAPP_TOKEN` is set.

## Tests

```bash
pip install pytest
python -m pytest tests/
```

## Deploy (Render)

`render.yaml` included: New → Blueprint → pick this repo. Set the secret env vars
(`WHATSAPP_TOKEN`, `WHATSAPP_APP_SECRET`, `VERIFY_TOKEN`, `OPENAI_API_KEY`, `ADMIN_TOKEN`)
in the Render dashboard.

## Connecting real WhatsApp (per client)

1. BSP account (Twilio or 360dialog) — approved decision #3.
2. Register the client's WhatsApp Business number through the BSP → get `phone_number_id`.
3. Point the webhook to `https://<host>/webhook` with your `VERIFY_TOKEN`;
   inbound messages must arrive in Cloud API payload shape.
4. Create the tenant row (slug, business name, `phone_number_id`, owner phone, knowledge).
5. Owner gets hot-lead and human-handoff alerts on `owner_phone`.

## Layout

```
app/
  main.py        FastAPI app: webhook (verify + inbound), health, router wiring
  engine.py      conversation engine: tiers, lead qualification, handoff, kill switch
  whatsapp.py    Cloud API client + payload parsing + signature check (+ dry-run)
  dashboard.py   per-tenant HTML dashboard, stats API, admin overview
  models.py      Tenant / Customer(lead) / Conversation / Message
  seed_demo.py   demo tenant (plumber) for sales demos and regression tests
  llm/           provider interface, mock provider, OpenAI-compatible provider
tests/           pytest: engine, webhook, dashboard, admin auth
```

## MVP scope guardrails (from the spec)

- Inbound only — no proactive marketing messages in MVP (keeps quality rating safe).
- No medical / legal / financial advice; sensitive topics escalate to a human.
- Everything client-specific lives in the tenant knowledge base — zero custom code
  per client (keeps maintenance under 20 min/week/client).

## v2 (only after 5 paying clients)

Auto-billing / self-serve signup, Flutter dashboard app, voice-note transcription,
calendar/booking integration, more channels (Instagram, SMS).
