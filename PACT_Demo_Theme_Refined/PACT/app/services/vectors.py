"""Dependency-free text vectoriser (hashed TF-IDF-style features with stemming, synonyms and bigrams).

Used as the always-available semantic fallback; real LLM embeddings are blended in when a model is configured.
"""
import math, re, zlib

DIM = 512
STOP = set("the and for with that this from are our you your have has can need needs offer offers will into more such "
           "their about help support also very using use who what want looking provide providing available".split())
SYN = {"money": "fund", "funding": "fund", "finance": "fund", "financial": "fund", "csr": "fund", "grant": "fund", "sponsor": "fund",
       "coder": "develop", "programmer": "develop", "engineer": "develop", "developer": "develop", "software": "develop",
       "website": "web", "app": "mobile", "apps": "mobile", "android": "mobile", "teacher": "train", "trainer": "train",
       "training": "train", "mentor": "train", "mentoring": "train", "mentorship": "train", "volunteer": "volunt",
       "volunteers": "volunt", "student": "volunt", "students": "volunt", "ml": "learn", "ai": "learn", "machine": "learn",
       "analytics": "data", "dataset": "data", "datasets": "data", "dashboard": "data", "doctor": "medic", "doctors": "medic",
       "clinic": "medic", "hospital": "medic", "health": "medic", "solar": "energi", "energy": "energi", "renewable": "energi"}


def stem(w: str) -> str:
    w = SYN.get(w, w)
    for suf in ("ing", "ers", "er", "ions", "ion", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    return SYN.get(w, w)


def tokens(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-z]{2,}", (text or "").lower()) if w not in STOP]


def embed(text: str) -> list[float]:
    toks = tokens(text)
    vec = [0.0] * DIM
    feats = toks + [a + "_" + b for a, b in zip(toks, toks[1:])]
    for f in feats:
        h = zlib.crc32(f.encode())
        vec[h % DIM] += (1.0 if h & 0x80000000 else -1.0) * (0.6 if "_" in f else 1.0)
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return max(0.0, sum(x * y for x, y in zip(a, b)))


def overlap(a: str, b: str) -> list[str]:
    """Human-readable shared concepts between two texts (for match explanations)."""
    ta = {stem(w): w for w in re.findall(r"[a-z]{3,}", a.lower()) if w not in STOP}
    tb = {stem(w): w for w in re.findall(r"[a-z]{3,}", b.lower()) if w not in STOP}
    return sorted(ta[k] for k in ta.keys() & tb.keys())
