"""Notifications, analytics, exports and admin endpoints."""
import csv, io
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import admin_only, audit, current_org, current_user, org_dict
from ..models import AuditLog, ImpactMetric, Listing, Notification, Organization, Partnership, User, now
from ..services import matching, sdg

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), u: User = Depends(current_user)):
    rows = db.query(Notification).filter(Notification.user_id == u.id).order_by(Notification.id.desc()).limit(30).all()
    return [{"id": n.id, "text": n.text, "link": n.link, "read": n.read, "created_at": n.created_at.isoformat()} for n in rows]


@router.post("/notifications/read")
def read_all(db: Session = Depends(get_db), u: User = Depends(current_user)):
    db.query(Notification).filter(Notification.user_id == u.id).update({"read": True}); db.commit()
    return {"ok": True}


@router.get("/analytics/overview")
def overview(db: Session = Depends(get_db), _: Organization = Depends(current_org)):
    orgs = db.query(Organization).all()
    listings = db.query(Listing).filter(Listing.status == "open").all()
    parts = db.query(Partnership).all()
    sdg_cov = Counter(s for o in orgs for s in (o.sdgs or []))
    weeks = []
    for i in range(7, -1, -1):
        start = now() - timedelta(weeks=i + 1); end = now() - timedelta(weeks=i)
        weeks.append({"label": end.strftime("%d %b"), "count": sum(1 for p in parts if start <= p.created_at < end)})
    need_tags = Counter(t for l in listings if l.kind == "need" for t in (l.tags or []))
    offer_tags = Counter(t for l in listings if l.kind == "offer" for t in (l.tags or []))
    demand = [{"tag": t, "needs": c, "offers": offer_tags.get(t, 0)} for t, c in need_tags.most_common(8)]
    return {
        "orgs": len(orgs), "verified": sum(o.verified for o in orgs),
        "open_needs": sum(l.kind == "need" for l in listings), "open_offers": sum(l.kind == "offer" for l in listings),
        "partnerships": Counter(p.status for p in parts), "types": Counter(o.type for o in orgs),
        "sdg_coverage": {str(k): v for k, v in sorted(sdg_cov.items())}, "weekly": weeks, "demand": demand,
        "gaps": matching.gap_analysis(db)[:6],
        "completion_rate": round(100 * sum(p.status == "completed" for p in parts) / max(1, sum(p.status in ("active", "completed") for p in parts))),
    }


@router.get("/analytics/impact")
def impact(db: Session = Depends(get_db), org: Organization = Depends(current_org)):
    parts = db.query(Partnership).filter((Partnership.org_a_id == org.id) | (Partnership.org_b_id == org.id)).all()
    by_sdg: dict[int, list] = {}
    for p in parts:
        for m in p.metrics:
            by_sdg.setdefault(m.sdg, []).append({"name": m.name, "value": m.value, "unit": m.unit, "partnership": p.title,
                                            "verification_status": m.verification_status, "evidence_url": m.evidence_url,
                                            "verification_note": m.verification_note})
    ms = [m for p in parts for m in p.milestones]
    return {"partnerships": len(parts), "active": sum(p.status == "active" for p in parts),
            "completed": sum(p.status == "completed" for p in parts),
            "milestones_total": len(ms), "milestones_done": sum(m.done for m in ms),
            "sdgs": {str(k): {"title": sdg.SDGS[k][0], "metrics": v} for k, v in sorted(by_sdg.items()) if k in sdg.SDGS},
            "trust": round(100 * matching.trust_score(db, org))}


@router.get("/analytics/network")
def network(db: Session = Depends(get_db), _: Organization = Depends(current_org)):
    parts = db.query(Partnership).filter(Partnership.status.in_(["active", "completed", "negotiating"])).all()
    return {"nodes": [org_dict(db, o) for o in db.query(Organization).all()],
            "edges": [{"a": p.org_a_id, "b": p.org_b_id, "status": p.status, "title": p.title} for p in parts]}


@router.get("/export/partnerships.csv")
def export_csv(db: Session = Depends(get_db), org: Organization = Depends(current_org)):
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["id", "title", "partner", "status", "match_score", "progress_%", "created", "updated"])
    for p in db.query(Partnership).filter((Partnership.org_a_id == org.id) | (Partnership.org_b_id == org.id)):
        other = p.org_b if p.org_a_id == org.id else p.org_a
        ms = p.milestones
        w.writerow([p.id, p.title, other.name, p.status, p.match_score, round(100 * sum(m.done for m in ms) / len(ms)) if ms else 0,
                    p.created_at.date(), p.updated_at.date()])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=partnerships.csv"})


# ---------- admin ----------
@router.get("/admin/overview")
def admin_overview(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    review_rows = db.query(ImpactMetric).filter(ImpactMetric.verification_status == "pending_review").order_by(ImpactMetric.recorded_at.desc()).all()
    impact_review = []
    for metric in review_rows:
        partnership = db.get(Partnership, metric.partnership_id)
        if partnership:
            impact_review.append({"id": metric.id, "name": metric.name, "value": metric.value, "unit": metric.unit,
                                  "sdg": metric.sdg, "evidence_url": metric.evidence_url, "partnership": partnership.title,
                                  "org_a": partnership.org_a.name, "org_b": partnership.org_b.name,
                                  "recorded_at": metric.recorded_at.isoformat()})
    return {"users": [{"id": u.id, "email": u.email, "name": u.full_name, "role": u.role, "active": u.is_active,
                       "org": u.org.name if u.org else None} for u in db.query(User).order_by(User.id).all()],
            "pending": [org_dict(db, o) for o in db.query(Organization).filter(Organization.verified == False).all()],  # noqa: E712
            "impact_review": impact_review,
            "audit": [{"id": a.id, "action": a.action, "detail": a.detail, "user_id": a.user_id, "at": a.created_at.isoformat()}
                      for a in db.query(AuditLog).order_by(AuditLog.id.desc()).limit(40)]}


@router.post("/admin/users/{uid}/toggle")
def toggle_user(uid: int, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u or u.id == admin.id:
        raise HTTPException(422, "You can't change this account.")
    u.is_active = not u.is_active; audit(db, admin, "user.toggle", u.email); db.commit()
    return {"ok": True, "active": u.is_active}


class ImpactReviewIn(BaseModel):
    status: str
    note: str = Field(default="", max_length=1000)


@router.post("/admin/impact/{metric_id}/review")
def review_impact(metric_id: int, body: ImpactReviewIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    metric = db.get(ImpactMetric, metric_id)
    if not metric:
        raise HTTPException(404, "Impact metric not found.")
    if body.status not in ("verified", "rejected"):
        raise HTTPException(422, "Status must be verified or rejected.")
    if body.status == "verified" and not metric.evidence_url:
        raise HTTPException(422, "Evidence URL is required before verification.")
    metric.verification_status = body.status
    metric.verification_note = body.note.strip()
    metric.verified_by = admin.id
    metric.verified_at = now()
    audit(db, admin, "impact." + body.status, f"metric #{metric.id}: {metric.name}")
    db.commit()
    return {"ok": True, "id": metric.id, "verification_status": metric.verification_status}
