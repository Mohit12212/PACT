import re

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuditLog, Notification, Organization, User
from .security import limiter, read_token
from .services import matching
from .services.realtime import hub


def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    uid = read_token(authorization.removeprefix("Bearer ").strip())
    user = db.get(User, uid) if uid else None
    if not user or not user.is_active:
        raise HTTPException(401, "Please sign in again.")
    return user


def current_org(user: User = Depends(current_user)) -> Organization:
    if not user.org:
        raise HTTPException(403, "Your account is not linked to an organisation.")
    return user.org


def admin_only(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrators only.")
    return user


def rate_limit(limit: int, window: int = 60):
    def dep(request: Request):
        if not limiter.allow(f"{request.url.path}:{request.client.host if request.client else '-'}", limit, window):
            raise HTTPException(429, "Too many requests. Wait a minute and try again.")
    return dep


def audit(db: Session, user: User | None, action: str, detail: str = ""):
    db.add(AuditLog(user_id=user.id if user else None, action=action, detail=detail[:300]))


async def notify_org(db: Session, org_id: int, text: str, link: str = "", skip_user: int | None = None):
    ids = []
    for u in db.query(User).filter(User.org_id == org_id, User.is_active == True).all():  # noqa: E712
        if u.id != skip_user:
            db.add(Notification(user_id=u.id, text=text, link=link))
            ids.append(u.id)
    db.commit()
    await hub.push(ids, {"type": "notification", "text": text, "link": link})


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def org_dict(db: Session, o: Organization, full: bool = False) -> dict:
    d = {"id": o.id, "name": o.name, "type": o.type, "sector": o.sector, "country": o.country, "city": o.city,
         "sdgs": o.sdgs or [], "verified": o.verified, "trust": round(100 * matching.trust_score(db, o))}
    if full:
        d.update(description=o.description, website=o.website, lat=o.lat, lon=o.lon,
                 listings=[listing_dict(l) for l in sorted(o.listings, key=lambda l: -l.id)])
    return d


def listing_dict(l, score=None) -> dict:
    d = {"id": l.id, "org_id": l.org_id, "org": l.org.name, "org_type": l.org.type, "org_verified": l.org.verified,
         "kind": l.kind, "title": l.title, "description": l.description, "tags": l.tags or [], "sdgs": l.sdgs or [],
         "remote_ok": l.remote_ok, "status": l.status, "created_at": l.created_at.isoformat()}
    if score is not None:
        d["relevance"] = score
    return d
