"""UN SDG catalogue plus an offline keyword classifier used when no LLM is available."""
import re

SDGS = {
    1: ("No Poverty", "#E5243B"), 2: ("Zero Hunger", "#DDA63A"), 3: ("Good Health & Well-being", "#4C9F38"),
    4: ("Quality Education", "#C5192D"), 5: ("Gender Equality", "#FF3A21"), 6: ("Clean Water & Sanitation", "#26BDE2"),
    7: ("Affordable & Clean Energy", "#FCC30B"), 8: ("Decent Work & Growth", "#A21942"),
    9: ("Industry, Innovation & Infrastructure", "#FD6925"), 10: ("Reduced Inequalities", "#DD1367"),
    11: ("Sustainable Cities & Communities", "#FD9D24"), 12: ("Responsible Consumption", "#BF8B2E"),
    13: ("Climate Action", "#3F7E44"), 14: ("Life Below Water", "#0A97D9"), 15: ("Life on Land", "#56C02B"),
    16: ("Peace, Justice & Institutions", "#00689D"), 17: ("Partnerships for the Goals", "#19486A"),
}

KEYWORDS = {
    1: "poverty livelihood microfinance income subsidy welfare", 2: "hunger food nutrition farming agriculture crop farmer",
    3: "health doctor clinic hospital medical vaccine mental wellbeing nurse", 4: "education school student teaching training literacy scholarship learning curriculum internship",
    5: "women gender girls maternal empowerment", 6: "water sanitation hygiene sensor purification groundwater",
    7: "solar energy renewable electricity grid battery", 8: "jobs employment skills entrepreneurship startup livelihood workforce",
    9: "technology software developer app platform innovation infrastructure research cloud data machine learning ai",
    10: "inequality inclusion disability marginalised refugee rural", 11: "city urban housing transport waste community",
    12: "recycling waste circular consumption sustainable packaging", 13: "climate carbon emissions tree plantation afforestation environment",
    14: "ocean marine river fish coastal plastic", 15: "forest biodiversity wildlife tree land soil",
    16: "governance justice transparency policy rights legal government",
}


def classify(text: str, limit: int = 4) -> list[int]:
    words = set(re.findall(r"[a-z]{3,}", (text or "").lower()))
    scored = []
    for sdg, kws in KEYWORDS.items():
        hits = sum(1 for k in kws.split() if k in words or any(w.startswith(k) for w in words))
        if hits:
            scored.append((hits, sdg))
    scored.sort(reverse=True)
    return sorted(s for _, s in scored[:limit])


def clean(ids) -> list[int]:
    out = set()
    for x in ids or []:
        try:
            if 1 <= int(x) <= 16:
                out.add(int(x))
        except (TypeError, ValueError):
            pass
    return sorted(out)
