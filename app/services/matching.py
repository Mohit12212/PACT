"""Hybrid, explainable matching engine.

For every (need, offer) pair between two organisations we combine five signals:
  semantic similarity (LLM embeddings when available, hashed vectors otherwise)   45%
  SDG overlap (Jaccard, SDG 17 excluded)                                            15%
  geography (haversine decay; remote-friendly listings are never penalised)         15%
  trust (verification, ratings, completed partnerships, profile completeness)       15%
  reciprocity (the other side also needs something this org offers)                 10%
The result keeps the per-signal breakdown so the UI can show *why* two organisations were matched.
"""
import math
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Listing, Organization, Partnership, Review
from . import vectors

W = {"semantic": 0.45, "sdg": 0.15, "geo": 0.15, "trust": 0.15, "reciprocity": 0.10}


def haversine(a, b) -> float | None:
    if None in (a.lat, a.lon, b.lat, b.lon):
        return None
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def trust_score(db: Session, org: Organization) -> float:
    """0..1 composite: verification 35%, ratings 30%, completed work 20%, profile completeness 15%."""
    avg = db.query(func.avg(Review.rating)).filter(Review.reviewee_org_id == org.id).scalar()
    done = db.query(Partnership).filter(Partnership.status == "completed",
                                        (Partnership.org_a_id == org.id) | (Partnership.org_b_id == org.id)).count()
    fields = [org.description, org.website, org.country, org.sector, org.sdgs]
    complete = sum(1 for f in fields if f) / len(fields)
    return round(0.35 * (1 if org.verified else 0) + 0.30 * ((avg or 3) / 5 if avg else 0.5) + 0.20 * min(done, 5) / 5 + 0.15 * complete, 3)


def jaccard(a, b) -> float:
    a, b = set(a or []) - {17}, set(b or []) - {17}
    return len(a & b) / len(a | b) if a | b else 0.0


def geo_score(need: Listing, offer: Listing, dist: float | None) -> float:
    if dist is None:
        return 0.6  # unknown location: neutral
    if need.remote_ok and offer.remote_ok:
        return max(0.7, math.exp(-dist / 4000))  # remote work: distance barely matters
    return math.exp(-dist / 400)


def sim(a: Listing, b: Listing) -> float:
    if a.embedding and b.embedding and a.embed_model and a.embed_model == b.embed_model:
        s = vectors.cosine(a.embedding, b.embedding)
    else:
        s = vectors.cosine(vectors.embed(a.text), vectors.embed(b.text))
    return min(1.0, s * 1.35)  # hashed cosines run low; gentle calibration


@dataclass
class Pair:
    need: Listing
    offer: Listing
    semantic: float
    sdg: float
    geo: float
    shared: list = field(default_factory=list)

    @property
    def raw(self):
        return W["semantic"] * self.semantic + W["sdg"] * self.sdg + W["geo"] * self.geo


def pairs_between(me_needs, other_offers):
    out = []
    for n in me_needs:
        for o in other_offers:
            p = Pair(n, o, sim(n, o), jaccard(n.sdgs, o.sdgs), 0.6)
            p.shared = vectors.overlap(n.text, o.text)[:6]
            out.append(p)
    return out


def match_org(db: Session, me: Organization, limit: int = 12, min_score: float = 12) -> list[dict]:
    my_needs = [l for l in me.listings if l.kind == "need" and l.status == "open"]
    my_offers = [l for l in me.listings if l.kind == "offer" and l.status == "open"]
    results = []
    for other in db.query(Organization).filter(Organization.id != me.id).all():
        o_needs = [l for l in other.listings if l.kind == "need" and l.status == "open"]
        o_offers = [l for l in other.listings if l.kind == "offer" and l.status == "open"]
        dist = haversine(me, other)
        fwd = pairs_between(my_needs, o_offers)   # they can give what I need
        rev = pairs_between(o_needs, my_offers)   # I can give what they need
        for p in fwd + rev:
            p.geo = geo_score(p.need, p.offer, dist)
        best_f = sorted(fwd, key=lambda p: -p.raw)[:2]
        best_r = sorted(rev, key=lambda p: -p.raw)[:2]
        if not best_f and not best_r:
            continue
        sem = max([p.semantic for p in best_f + best_r] or [0])
        sdg = max([p.sdg for p in best_f + best_r] or [0])
        geo = max([p.geo for p in best_f + best_r] or [0.6])
        recip = 1.0 if (best_f and best_r and best_r[0].semantic > 0.25 and best_f[0].semantic > 0.25) else (0.4 if best_f and best_r else 0.0)
        trust = trust_score(db, other)
        total = 100 * (W["semantic"] * sem + W["sdg"] * sdg + W["geo"] * geo + W["trust"] * trust + W["reciprocity"] * recip)
        if total < min_score or sem < 0.12:
            continue
        results.append({
            "org_id": other.id, "score": round(total, 1), "mutual": recip == 1.0,
            "distance_km": round(dist) if dist is not None else None,
            "breakdown": {"semantic": round(sem * 100), "sdg": round(sdg * 100), "geo": round(geo * 100),
                          "trust": round(trust * 100), "reciprocity": round(recip * 100)},
            "they_give": [pair_dict(p) for p in best_f if p.semantic > 0.12],
            "you_give": [pair_dict(p) for p in best_r if p.semantic > 0.12],
            "shared_sdgs": sorted((set(me.sdgs or []) & set(other.sdgs or [])) - {17}),
        })
    return sorted(results, key=lambda r: -r["score"])[:limit]


def pair_dict(p: Pair) -> dict:
    return {"need_id": p.need.id, "need": p.need.title, "offer_id": p.offer.id, "offer": p.offer.title,
            "similarity": round(p.semantic * 100), "shared_terms": p.shared}


def search_listings(db: Session, query: str, kind: str | None, sdg: int | None, limit: int = 30):
    """Semantic + keyword listing search for the marketplace."""
    q = db.query(Listing).filter(Listing.status == "open")
    if kind in ("need", "offer"):
        q = q.filter(Listing.kind == kind)
    rows = [l for l in q.all() if not sdg or sdg in (l.sdgs or [])]
    if not query.strip():
        return sorted(rows, key=lambda l: -l.id)[:limit], {}
    qv, scores = vectors.embed(query), {}
    qwords = set(vectors.tokens(query))
    for l in rows:
        lex = len(qwords & set(vectors.tokens(l.text))) / (len(qwords) or 1)
        scores[l.id] = round(100 * min(1.0, 0.65 * vectors.cosine(qv, vectors.embed(l.text)) * 1.35 + 0.35 * lex))
    ranked = [l for l in sorted(rows, key=lambda l: -scores[l.id]) if scores[l.id] >= 8]
    return ranked[:limit], scores


def gap_analysis(db: Session, threshold: float = 0.3) -> list[dict]:
    """Open needs that no other organisation's offer covers - the platform's 'unmet demand' signal."""
    needs = db.query(Listing).filter(Listing.kind == "need", Listing.status == "open").all()
    offers = db.query(Listing).filter(Listing.kind == "offer", Listing.status == "open").all()
    out = []
    for n in needs:
        best = max([sim(n, o) for o in offers if o.org_id != n.org_id] or [0])
        if best < threshold:
            out.append({"listing_id": n.id, "title": n.title, "org": n.org.name, "best_similarity": round(best * 100), "sdgs": n.sdgs})
    return sorted(out, key=lambda x: x["best_similarity"])
