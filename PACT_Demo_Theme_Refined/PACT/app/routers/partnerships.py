from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import audit, current_org, current_user, notify_org, org_dict
from ..models import ImpactMetric, Message, Milestone, Organization, Partnership, Review, User
from ..services.realtime import hub

router = APIRouter(prefix="/api/partnerships", tags=["partnerships"])

# who may move a partnership to which status
FLOW = {
    "proposed": {"negotiating": "receiver", "declined": "any"},
    "negotiating": {"active": "any", "declined": "any"},
    "active": {"completed": "any"},
}


class ProposalIn(BaseModel):
    org_id: int
    title: str = Field(min_length=3, max_length=200)
    summary: str = ""
    match_score: float = 0
    milestones: list[str] = []


class StatusIn(BaseModel):
    status: str


class MilestoneIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    due: str = ""


class MetricIn(BaseModel):
    sdg: int = Field(ge=1, le=17)
    name: str = Field(min_length=2, max_length=120)
    value: float
    unit: str = ""
    evidence_url: str = Field(default="", max_length=500)

    @field_validator("evidence_url")
    @classmethod
    def validate_evidence_url(cls, value: str) -> str:
        value = value.strip()
        if value and not value.lower().startswith(("https://", "http://")):
            raise ValueError("Evidence URL must use http:// or https://")
        return value


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""


def mine_or_404(db: Session, pid: int, org: Organization) -> Partnership:
    p = db.get(Partnership, pid)
    if not p or org.id not in (p.org_a_id, p.org_b_id):
        raise HTTPException(404, "Partnership not found.")
    return p


def p_dict(db, p: Partnership, org: Organization, detail=False) -> dict:
    other = p.org_b if p.org_a_id == org.id else p.org_a
    ms = p.milestones
    d = {"id": p.id, "title": p.title, "summary": p.summary, "status": p.status, "match_score": p.match_score,
         "you_initiated": p.org_a_id == org.id, "other": org_dict(db, other),
         "progress": round(100 * sum(m.done for m in ms) / len(ms)) if ms else 0,
         "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat()}
    if detail:
        d["milestones"] = [{"id": m.id, "title": m.title, "due": m.due, "done": m.done} for m in ms]
        d["metrics"] = [{"id": m.id, "sdg": m.sdg, "name": m.name, "value": m.value, "unit": m.unit,
                         "evidence_url": m.evidence_url, "verification_status": m.verification_status,
                         "verification_note": m.verification_note, "verified_at": m.verified_at.isoformat() if m.verified_at else None}
                        for m in p.metrics]
        d["messages"] = [msg_dict(m) for m in p.messages[-200:]]
        d["reviews"] = [{"rating": r.rating, "comment": r.comment, "mine": r.reviewer_org_id == org.id} for r in p.reviews]
        d["you_reviewed"] = any(r.reviewer_org_id == org.id for r in p.reviews)
        d["me"] = org_dict(db, org)
    return d


def msg_dict(m: Message) -> dict:
    return {"id": m.id, "partnership_id": m.partnership_id, "org_id": m.org_id, "user": m.user.full_name,
            "body": m.body, "created_at": m.created_at.isoformat()}


@router.get("")
def mine(status: str = "", db: Session = Depends(get_db), org: Organization = Depends(current_org)):
    q = db.query(Partnership).filter((Partnership.org_a_id == org.id) | (Partnership.org_b_id == org.id))
    if status:
        q = q.filter(Partnership.status == status)
    return [p_dict(db, p, org) for p in q.order_by(Partnership.updated_at.desc()).all()]


@router.post("")
async def propose(b: ProposalIn, org: Organization = Depends(current_org), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if b.org_id == org.id:
        raise HTTPException(422, "You can't partner with your own organisation.")
    other = db.get(Organization, b.org_id)
    if not other:
        raise HTTPException(404, "Organisation not found.")
    live = db.query(Partnership).filter(Partnership.status.in_(["proposed", "negotiating", "active"]),
        ((Partnership.org_a_id == org.id) & (Partnership.org_b_id == other.id)) | ((Partnership.org_a_id == other.id) & (Partnership.org_b_id == org.id))).first()
    if live:
        raise HTTPException(409, "You already have a live partnership with this organisation.")
    p = Partnership(org_a_id=org.id, org_b_id=other.id, title=b.title.strip(), summary=b.summary, match_score=b.match_score)
    p.milestones = [Milestone(title=t.strip()) for t in b.milestones if t.strip()][:8]
    db.add(p); audit(db, user, "partnership.propose", f"{org.name} -> {other.name}"); db.commit()
    await notify_org(db, other.id, f"{org.name} proposed a partnership: {p.title}", f"#/partnership/{p.id}")
    return p_dict(db, p, org, detail=True)


@router.get("/{pid}")
def detail(pid: int, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    return p_dict(db, mine_or_404(db, pid, org), org, detail=True)


@router.post("/{pid}/status")
async def set_status(pid: int, b: StatusIn, org: Organization = Depends(current_org), user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = mine_or_404(db, pid, org)
    rule = FLOW.get(p.status, {}).get(b.status)
    if not rule:
        raise HTTPException(422, f"A {p.status} partnership can't move to {b.status}.")
    if rule == "receiver" and org.id != p.org_b_id:
        raise HTTPException(403, "Only the organisation that received the proposal can respond to it.")
    p.status = b.status
    audit(db, user, "partnership.status", f"#{p.id} -> {b.status}"); db.commit()
    other_id = p.org_b_id if p.org_a_id == org.id else p.org_a_id
    await notify_org(db, other_id, f"{org.name} moved “{p.title}” to {b.status}.", f"#/partnership/{p.id}")
    return p_dict(db, p, org, detail=True)


@router.post("/{pid}/milestones")
def add_milestone(pid: int, b: MilestoneIn, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    p = mine_or_404(db, pid, org)
    p.milestones.append(Milestone(title=b.title.strip(), due=b.due)); db.commit()
    return p_dict(db, p, org, detail=True)


@router.post("/{pid}/milestones/{mid}/toggle")
async def toggle_milestone(pid: int, mid: int, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    p = mine_or_404(db, pid, org)
    m = next((m for m in p.milestones if m.id == mid), None)
    if not m:
        raise HTTPException(404, "Milestone not found.")
    m.done = not m.done; db.commit()
    if m.done:
        other_id = p.org_b_id if p.org_a_id == org.id else p.org_a_id
        await notify_org(db, other_id, f"Milestone completed: {m.title}", f"#/partnership/{p.id}")
    return p_dict(db, p, org, detail=True)


@router.post("/{pid}/metrics")
def add_metric(pid: int, b: MetricIn, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    p = mine_or_404(db, pid, org)
    p.metrics.append(ImpactMetric(sdg=b.sdg, name=b.name.strip(), value=b.value, unit=b.unit,
                                  evidence_url=b.evidence_url.strip(), verification_status="pending_review" if b.evidence_url.strip() else "self_reported")); db.commit()
    return p_dict(db, p, org, detail=True)


@router.post("/{pid}/messages")
async def post_message(pid: int, b: MessageIn, org: Organization = Depends(current_org), user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = mine_or_404(db, pid, org)
    m = Message(partnership_id=p.id, user_id=user.id, org_id=org.id, body=b.body.strip())
    db.add(m); db.commit(); db.refresh(m)
    ids = [u.id for oid in (p.org_a_id, p.org_b_id) for u in db.query(User).filter(User.org_id == oid).all()]
    await hub.push(ids, {"type": "message", "message": msg_dict(m)})
    return msg_dict(m)


@router.post("/{pid}/review")
async def review(pid: int, b: ReviewIn, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    p = mine_or_404(db, pid, org)
    if p.status != "completed":
        raise HTTPException(422, "You can review a partnership once it is completed.")
    if any(r.reviewer_org_id == org.id for r in p.reviews):
        raise HTTPException(409, "You already reviewed this partnership.")
    other_id = p.org_b_id if p.org_a_id == org.id else p.org_a_id
    p.reviews.append(Review(reviewer_org_id=org.id, reviewee_org_id=other_id, rating=b.rating, comment=b.comment)); db.commit()
    await notify_org(db, other_id, f"{org.name} left you a {b.rating}-star review.", f"#/partnership/{p.id}")
    return p_dict(db, p, org, detail=True)
