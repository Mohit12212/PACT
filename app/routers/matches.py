from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_org, org_dict
from ..models import Organization, Partnership
from ..services import matching

router = APIRouter(prefix="/api/matches", tags=["matching"])


def build(db: Session, org: Organization, limit: int = 12) -> list[dict]:
    busy = {(p.org_b_id if p.org_a_id == org.id else p.org_a_id): p.status for p in db.query(Partnership).filter(
        Partnership.status.in_(["proposed", "negotiating", "active"]),
        (Partnership.org_a_id == org.id) | (Partnership.org_b_id == org.id)).all()}
    out = []
    for m in matching.match_org(db, org, limit=limit):
        m["org"] = org_dict(db, db.get(Organization, m["org_id"]))
        m["existing"] = busy.get(m["org_id"])
        out.append(m)
    return out


@router.get("")
def my_matches(db: Session = Depends(get_db), org: Organization = Depends(current_org)):
    return build(db, org)


@router.get("/gaps")
def gaps(db: Session = Depends(get_db), org: Organization = Depends(current_org)):
    return matching.gap_analysis(db)
