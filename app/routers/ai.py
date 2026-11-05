"""AI features. Each one returns {text, ai}: ai=false means the offline fallback answered."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import admin_only, current_org, current_user
from ..models import Organization, Partnership, Setting, User
from ..services import llm, matching, sdg
from .matches import build

router = APIRouter(prefix="/api/ai", tags=["ai"])
SYSTEM = ("You are the partnership copilot of PACT, a platform that connects NGOs, colleges, startups, companies and "
          "governments to advance the UN SDGs (especially SDG 17). Be concrete, concise and practical.")


class SettingsIn(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    embed_model: str = ""


class TextIn(BaseModel):
    text: str


class OrgRef(BaseModel):
    org_id: int
    tone: str = "warm and professional"


class CopilotIn(BaseModel):
    message: str
    history: list[dict] = []


def _pair_ctx(db, me: Organization, other_id: int):
    other = db.get(Organization, other_id)
    if not other:
        raise HTTPException(404, "Organisation not found.")
    m = next((x for x in matching.match_org(db, me, limit=50, min_score=0) if x["org_id"] == other_id), None)
    return other, m


@router.get("/status")
async def status(_: User = Depends(current_user)):
    cfg = llm.get_cfg()
    return {"up": await llm.is_up(), "model": cfg["model"], "embed_model": cfg["embed_model"], "base_url": cfg["base_url"]}


@router.get("/models")
async def models(base: str = "", key: str = "", _: User = Depends(current_user)):
    try:
        return {"ok": True, "models": await llm.list_models(base or None, key or None)}
    except Exception as e:
        return {"ok": False, "models": [], "error": f"Could not reach the AI server: {e}"}


@router.post("/settings")
def save_settings(b: SettingsIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    values = b.model_dump()
    # An empty API-key field means "keep the saved key"; keys are never echoed back.
    if not values.get("api_key"):
        values.pop("api_key", None)
    for k, v in values.items():
        db.merge(Setting(k=k, v=v))
    db.commit()
    return {"ok": True}


@router.get("/settings")
def get_settings(_: User = Depends(admin_only)):
    c = llm.get_cfg(); c["api_key"] = "set" if c["api_key"] else ""
    return c


@router.post("/test")
async def test(_: User = Depends(admin_only)):
    try:
        return {"ok": True, "reply": await llm.chat("Reply with exactly: PACT AI is ready.", temp=0)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/tag")
async def tag(b: TextIn, _: User = Depends(current_user)):
    fallback = sdg.classify(b.text)
    try:
        out = await llm.chat(f"{b.text}\n\nWhich UN SDGs (1-16) does this support? Answer ONLY with up to 4 comma-separated numbers.", temp=0.1)
        ids = sdg.clean(__import__("re").findall(r"\d+", out))
        return {"sdgs": ids or fallback, "ai": bool(ids)}
    except Exception:
        return {"sdgs": fallback, "ai": False}


@router.post("/explain")
async def explain(b: OrgRef, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    other, m = _pair_ctx(db, org, b.org_id)
    gives = "; ".join(f"{p['offer']} (for your need: {p['need']})" for p in (m or {}).get("they_give", [])) or "nothing directly matched yet"
    gets = "; ".join(f"{p['need']} (you can offer: {p['offer']})" for p in (m or {}).get("you_give", [])) or "nothing directly matched yet"
    try:
        text = await llm.chat(f"{org.name} ({org.type}) and {other.name} ({other.type}).\n{other.name} can give: {gives}.\n{org.name} can give: {gets}.\n"
                              f"Match score {m['score'] if m else 0}/100. In 3 sentences explain why this is a strong partnership, "
                              "the biggest risk to watch, and which SDG 17 target (17.16 or 17.17) it advances.", SYSTEM, 0.3)
        return {"text": text, "ai": True}
    except Exception:
        return {"ai": False, "text": f"{other.name} can contribute {gives}. In return {org.name} can contribute {gets}. "
                f"Overall fit is {m['score'] if m else 0}/100, combining semantic similarity, shared SDGs, location and trust. "
                "This cross-sector partnership supports SDG 17.17 (effective public, private and civil-society partnerships)."}


@router.post("/outreach")
async def outreach(b: OrgRef, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    other, m = _pair_ctx(db, org, b.org_id)
    ask = ", ".join(p["offer"] for p in (m or {}).get("they_give", [])) or "your expertise"
    give = ", ".join(p["offer"] for p in (m or {}).get("you_give", [])) or "our experience"
    try:
        text = await llm.chat(f"Write a partnership outreach message from {org.name} ({org.type}) to {other.name} ({other.type}). "
                              f"We would like: {ask}. We can offer: {give}. Tone: {b.tone}. Under 120 words, mention SDG 17, end with a clear call to action.", SYSTEM)
        return {"text": text, "ai": True}
    except Exception:
        return {"ai": False, "text": f"Dear {other.name} team,\n\nWe are {org.name}. Your work on {ask} is a strong fit with what we are building, and we can offer {give} in return. "
                f"A partnership would advance SDG 17 and our shared goals.\n\nCould we schedule a 20-minute call this week?\n\nBest regards,\n{org.name}"}


@router.post("/plan")
async def plan(b: OrgRef, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    """Drafts a partnership title, summary and milestones the user can accept in one click."""
    other, m = _pair_ctx(db, org, b.org_id)
    gives = [p["offer"] for p in (m or {}).get("they_give", [])]
    gets = [p["offer"] for p in (m or {}).get("you_give", [])]
    fallback = {"title": f"{org.name} × {other.name}: {(gives or ['shared goals'])[0]}",
                "summary": f"{other.name} provides {', '.join(gives) or 'support'}; {org.name} provides {', '.join(gets) or 'delivery capacity'}.",
                "milestones": ["Kick-off call and scope agreement", *[f"Deliver: {g}" for g in (gives + gets)[:3]], "Mid-point review", "Measure impact and publish a short report"]}
    try:
        out = await llm.chat(f"Plan a partnership between {org.name} and {other.name}. They give: {gives}. We give: {gets}. "
                             'Return ONLY JSON: {"title":"...","summary":"max 40 words","milestones":["5 short milestones"]}', SYSTEM, 0.2)
        d = llm.parse_json(out)
        if isinstance(d, dict) and d.get("milestones"):
            return {**fallback, **{k: d[k] for k in ("title", "summary", "milestones") if k in d}, "ai": True}
    except Exception:
        pass
    return {**fallback, "ai": False}


@router.post("/copilot")
async def copilot(b: CopilotIn, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    matches = build(db, org, limit=5)
    live = db.query(Partnership).filter((Partnership.org_a_id == org.id) | (Partnership.org_b_id == org.id)).all()
    ctx = (f"My organisation: {org.name} ({org.type}, {org.sector}). Needs: {[l.title for l in org.listings if l.kind == 'need' and l.status == 'open']}. "
           f"Offers: {[l.title for l in org.listings if l.kind == 'offer' and l.status == 'open']}.\n"
           f"Top matches: " + "; ".join(f"{m['org']['name']} ({m['score']}/100, gives {[p['offer'] for p in m['they_give']]})" for m in matches) +
           f"\nMy partnerships: " + "; ".join(f"{p.title} [{p.status}]" for p in live))
    history = [h for h in b.history[-8:] if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str)]
    try:
        text = await llm.chat(f"Context:\n{ctx}\n\nQuestion: {b.message}", SYSTEM, 0.4, history)
        return {"text": text, "ai": True}
    except Exception:
        top = matches[:3]
        lines = "\n".join(f"- {m['org']['name']} ({m['score']}/100): can give {', '.join(p['offer'] for p in m['they_give']) or 'n/a'}" for m in top)
        return {"ai": False, "text": f"The AI model is offline, so here is what the matching engine found for {org.name}:\n{lines or 'No matches yet. Add more needs and offers.'}\n\nConnect a local model in Settings for full conversations."}


@router.post("/report")
async def report(org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    parts = db.query(Partnership).filter((Partnership.org_a_id == org.id) | (Partnership.org_b_id == org.id)).all()
    if not parts:
        raise HTTPException(422, "Create a partnership first, then generate a report.")
    lines = "\n".join(f"- {p.title} with {(p.org_b if p.org_a_id == org.id else p.org_a).name} [{p.status}], "
                      f"{sum(m.done for m in p.milestones)}/{len(p.milestones)} milestones; impact: "
                      + ", ".join(f"{m.name} {m.value:g} {m.unit} (SDG {m.sdg})" for m in p.metrics) for p in parts)
    try:
        return {"ai": True, "text": await llm.chat(f"Write a one-page SDG 17 partnership impact report for {org.name} with headings Summary, Partnerships, SDG impact, "
                                                   f"Recommendations. Use only these facts:\n{lines}", SYSTEM, 0.3)}
    except Exception:
        return {"ai": False, "text": f"# Partnership impact report: {org.name}\n\n## Summary\n{len(parts)} partnership(s) tracked, "
                f"{sum(p.status == 'active' for p in parts)} active and {sum(p.status == 'completed' for p in parts)} completed.\n\n## Partnerships\n{lines}\n"}
