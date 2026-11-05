from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import admin_only, audit, current_org, current_user, notify_org, org_dict
from ..models import ORG_TYPES, Listing, Organization, Review, User
from ..services import llm, matching, sdg, vectors

router = APIRouter(prefix="/api", tags=["organisations & listings"])


class OrgIn(BaseModel):
    name: str
    type: str = "NGO"
    sector: str = ""
    description: str = ""
    website: str = ""
    country: str = ""
    city: str = ""
    lat: float | None = None
    lon: float | None = None
    sdgs: list[int] = []


class ListingIn(BaseModel):
    kind: str
    title: str
    description: str = ""
    tags: list[str] = []
    sdgs: list[int] = []
    remote_ok: bool = True


@router.get("/orgs")
def list_orgs(q: str = "", type: str = "", sdg_id: int = 0, verified: bool = False,
              db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.query(Organization).all()
    out = [o for o in rows if (not q or q.lower() in f"{o.name} {o.sector} {o.description}".lower())
           and (not type or o.type == type) and (not sdg_id or sdg_id in (o.sdgs or [])) and (not verified or o.verified)]
    return [org_dict(db, o) for o in sorted(out, key=lambda o: -matching.trust_score(db, o))]


@router.get("/orgs/{org_id}")
def get_org(org_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    o = db.get(Organization, org_id)
    if not o:
        raise HTTPException(404, "Organisation not found.")
    d = org_dict(db, o, full=True)
    revs = db.query(Review).filter(Review.reviewee_org_id == o.id).order_by(Review.id.desc()).limit(5).all()
    d["reviews"] = [{"rating": r.rating, "comment": r.comment, "from": db.get(Organization, r.reviewer_org_id).name} for r in revs]
    return d


@router.put("/orgs/me")
def update_my_org(b: OrgIn, org: Organization = Depends(current_org), db: Session = Depends(get_db), u: User = Depends(current_user)):
    if b.type not in ORG_TYPES:
        raise HTTPException(422, "Unknown organisation type.")
    clash = db.query(Organization).filter(Organization.name == b.name.strip(), Organization.id != org.id).first()
    if clash:
        raise HTTPException(409, "That organisation name is taken.")
    for f in ("type", "sector", "description", "website", "country", "city", "lat", "lon"):
        setattr(org, f, getattr(b, f))
    org.name = b.name.strip()
    org.sdgs = sorted(set(sdg.clean(b.sdgs)) | {17})
    audit(db, u, "org.update", org.name); db.commit()
    return org_dict(db, org, full=True)


@router.post("/orgs/{org_id}/verify")
async def verify_org(org_id: int, on: bool = True, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    o = db.get(Organization, org_id)
    if not o:
        raise HTTPException(404, "Organisation not found.")
    o.verified = on
    audit(db, admin, "org.verify" if on else "org.unverify", o.name); db.commit()
    if on:
        await notify_org(db, o.id, "Your organisation is now verified. Your trust score has increased.", "#/profile")
    return org_dict(db, o)


# ---------- listings (needs & offers) ----------
async def _embed(l: Listing):
    res = await llm.embed_texts([l.text])
    l.embedding, l.embed_model = (res[0][0], res[1]) if res else (vectors.embed(l.text), "")


@router.get("/listings")
def search(q: str = "", kind: str = "", sdg_id: int = 0, mine: bool = False,
           db: Session = Depends(get_db), org: Organization = Depends(current_org)):
    if mine:
        rows = sorted(org.listings, key=lambda l: -l.id)
        return [listing_dict_(l) for l in rows]
    rows, scores = matching.search_listings(db, q, kind, sdg_id or None)
    return [listing_dict_(l, scores.get(l.id)) for l in rows]


def listing_dict_(l, score=None):
    from ..deps import listing_dict
    return listing_dict(l, score)


@router.post("/listings")
async def create_listing(b: ListingIn, org: Organization = Depends(current_org), db: Session = Depends(get_db), u: User = Depends(current_user)):
    if b.kind not in ("need", "offer") or len(b.title.strip()) < 3:
        raise HTTPException(422, "Pick need or offer and give it a title of at least 3 characters.")
    l = Listing(org_id=org.id, kind=b.kind, title=b.title.strip(), description=b.description, tags=[t.strip().lower() for t in b.tags if t.strip()][:8],
                sdgs=sdg.clean(b.sdgs) or sdg.classify(b.title + " " + b.description), remote_ok=b.remote_ok)
    await _embed(l)
    org.sdgs = sorted(set(org.sdgs or []) | set(l.sdgs) | {17})
    db.add(l); audit(db, u, "listing.create", l.title); db.commit()
    return listing_dict_(l)


@router.put("/listings/{lid}")
async def update_listing(lid: int, b: ListingIn, org: Organization = Depends(current_org), db: Session = Depends(get_db), u: User = Depends(current_user)):
    l = db.get(Listing, lid)
    if not l or l.org_id != org.id:
        raise HTTPException(404, "Listing not found.")
    l.title, l.description, l.tags, l.remote_ok = b.title.strip(), b.description, [t.strip().lower() for t in b.tags if t.strip()][:8], b.remote_ok
    l.sdgs = sdg.clean(b.sdgs) or l.sdgs
    await _embed(l)
    db.commit()
    return listing_dict_(l)


@router.post("/listings/{lid}/toggle")
def toggle_listing(lid: int, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    l = db.get(Listing, lid)
    if not l or l.org_id != org.id:
        raise HTTPException(404, "Listing not found.")
    l.status = "filled" if l.status == "open" else "open"
    db.commit()
    return listing_dict_(l)


@router.delete("/listings/{lid}")
def delete_listing(lid: int, org: Organization = Depends(current_org), db: Session = Depends(get_db)):
    l = db.get(Listing, lid)
    if not l or l.org_id != org.id:
        raise HTTPException(404, "Listing not found.")
    db.delete(l); db.commit()
    return {"ok": True}
