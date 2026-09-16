"""Minimal per-tenant dashboard (HTML) + JSON stats + admin overview."""
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Conversation, Customer, Tenant

router = APIRouter()

PAGE = """<!doctype html><html dir="rtl" lang="he"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title><style>
body{font-family:system-ui,Arial;margin:0;background:#f5f6f8;color:#222}
header{background:#111827;color:#fff;padding:14px 20px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
main{padding:20px;max-width:960px;margin:auto}
.card{background:#fff;border-radius:10px;padding:16px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.stats{display:flex;gap:12px;flex-wrap:wrap}
.stat{background:#fff;border-radius:10px;padding:14px 20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.stat b{font-size:24px;display:block}
table{width:100%%;border-collapse:collapse;font-size:14px}
th,td{padding:8px;border-bottom:1px solid #eee;text-align:right}
.badge{padding:2px 10px;border-radius:12px;font-size:12px;color:#fff}
.hot{background:#dc2626}.qualified{background:#d97706}.new{background:#6b7280}.handed_off{background:#7c3aed}.closed{background:#059669}
button{padding:8px 16px;border:0;border-radius:8px;cursor:pointer;font-size:14px}
.pause{background:#dc2626;color:#fff}.resume{background:#059669;color:#fff}
.msg{margin:6px 0;padding:8px 12px;border-radius:10px;max-width:80%%}
.in{background:#eef2f7}.out{background:#dcf8c6;margin-right:auto}
small{color:#666}
</style></head><body>%(body)s</body></html>"""


def _tenant_or_404(slug: str, db: Session) -> Tenant:
    t = db.query(Tenant).filter_by(slug=slug).first()
    if not t:
        raise HTTPException(404, "tenant not found")
    return t


@router.get("/dashboard/{slug}", response_class=HTMLResponse)
def dashboard(slug: str, db: Session = Depends(get_db)):
    t = _tenant_or_404(slug, db)
    customers = db.query(Customer).filter_by(tenant_id=t.id).all()
    convos = db.query(Conversation).filter_by(tenant_id=t.id).all()

    def count(status):
        return sum(1 for c in customers if c.status == status)

    rows = []
    for c in sorted(customers, key=lambda x: x.updated_at or x.created_at, reverse=True):
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                    "<td><span class='badge %s'>%s</span></td></tr>" % (
                        c.name or "-", c.wa_id, c.service or "-", c.urgency or "-",
                        c.area or "-", c.status, c.status))

    convo_blocks = []
    for cv in sorted(convos, key=lambda x: x.last_activity or x.created_at, reverse=True)[:20]:
        msgs = "".join(
            "<div class='msg %s'>%s <small>%s</small></div>" % (m.direction, m.body, m.tier or "")
            for m in cv.messages[-10:])
        mode = "\u05d1\u05df \u05d0\u05d3\u05dd" if cv.mode == "human" else "AI"
        convo_blocks.append("<div class='card'><b>%s</b> (%s) <small>%s</small>%s</div>" % (
            cv.customer.name or cv.customer.wa_id, cv.customer.wa_id, mode, msgs))

    toggle = ("<form method='post' action='/dashboard/%s/resume'><button class='resume'>\u05d4\u05e4\u05e2\u05dc \u05e1\u05d5\u05db\u05df</button></form>" % slug
              if t.agent_paused else
              "<form method='post' action='/dashboard/%s/pause'><button class='pause'>\u05e2\u05e6\u05d5\u05e8 \u05e1\u05d5\u05db\u05df</button></form>" % slug)

    body = (
        "<header><h2>%s</h2><span>%s</span>%s</header><main>"
        "<div class='stats'>"
        "<div class='stat'><b>%d</b>\u05e4\u05e0\u05d9\u05d5\u05ea</div>"
        "<div class='stat'><b>%d</b>\u05de\u05d5\u05e1\u05de\u05db\u05d9\u05dd</div>"
        "<div class='stat'><b>%d</b>\u05d7\u05de\u05d9\u05dd</div>"
        "<div class='stat'><b>%d</b>\u05d4\u05d5\u05e2\u05d1\u05e8\u05d5 \u05d0\u05dc\u05d9\u05da</div>"
        "</div>"
        "<div class='card'><h3>\u05dc\u05d9\u05d3\u05d9\u05dd</h3><table>"
        "<tr><th>\u05e9\u05dd</th><th>\u05d8\u05dc\u05e4\u05d5\u05df</th><th>\u05e9\u05d9\u05e8\u05d5\u05ea</th><th>\u05d3\u05d7\u05d9\u05e4\u05d5\u05ea</th><th>\u05d0\u05d6\u05d5\u05e8</th><th>\u05e1\u05d8\u05d8\u05d5\u05e1</th></tr>%s</table></div>"
        "<h3>\u05e9\u05d9\u05d7\u05d5\u05ea \u05d0\u05d7\u05e8\u05d5\u05e0\u05d5\u05ea</h3>%s</main>"
    ) % (
        t.business_name,
        "\u05d4\u05e1\u05d5\u05db\u05df \u05de\u05d5\u05e9\u05d4\u05d4" if t.agent_paused else "\u05d4\u05e1\u05d5\u05db\u05df \u05e4\u05e2\u05d9\u05dc",
        toggle,
        len(customers), count("qualified"), count("hot"), count("handed_off"),
        "".join(rows), "".join(convo_blocks),
    )
    return PAGE % {"title": t.business_name, "body": body}


@router.post("/dashboard/{slug}/pause")
def pause(slug: str, db: Session = Depends(get_db)):
    t = _tenant_or_404(slug, db)
    t.agent_paused = True
    db.commit()
    return RedirectResponse("/dashboard/%s" % slug, status_code=303)


@router.post("/dashboard/{slug}/resume")
def resume(slug: str, db: Session = Depends(get_db)):
    t = _tenant_or_404(slug, db)
    t.agent_paused = False
    db.commit()
    return RedirectResponse("/dashboard/%s" % slug, status_code=303)


@router.get("/api/{slug}/stats")
def stats(slug: str, db: Session = Depends(get_db)):
    t = _tenant_or_404(slug, db)
    customers = db.query(Customer).filter_by(tenant_id=t.id).all()
    out = {"tenant": t.slug, "business": t.business_name, "paused": t.agent_paused,
           "total_leads": len(customers)}
    for c in customers:
        out[c.status] = out.get(c.status, 0) + 1
    return out


@router.get("/api/admin/tenants")
def admin_tenants(x_admin_token: str = Header(""), db: Session = Depends(get_db)):
    if x_admin_token != settings.admin_token:
        raise HTTPException(401, "bad admin token")
    return [{"slug": t.slug, "business": t.business_name,
             "phone_number_id": t.phone_number_id, "paused": t.agent_paused}
            for t in db.query(Tenant).all()]
