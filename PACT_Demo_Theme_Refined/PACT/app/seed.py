"""Creates the admin account and a realistic demo network on first start (disable with SEED_DEMO=0)."""
import random
from datetime import timedelta

from .config import settings
from .db import SessionLocal
from .models import (ImpactMetric, Listing, Message, Milestone, Organization, Partnership, Review, User, now)
from .security import hash_password
from .services import llm, sdg, vectors

# name, type, sector, city, country, lat, lon, verified, description, needs[], offers[]  (title, description, tags)
ORGS = [
    ("GreenRoots NGO", "NGO", "Environment", "Chandigarh", "India", 30.73, 76.78, True,
     "Community tree-plantation network restoring degraded land across Punjab and Haryana.",
     [("Mobile app for tree tracking", "Android app so volunteers can geotag and monitor survival of planted saplings.", ["mobile", "app", "software"]),
      ("Web developers for volunteer portal", "Volunteer sign-up, event pages and a public planting map.", ["web", "developers", "volunteers"])],
     [("Tree plantation drives", "Organise and run plantation drives with trained local volunteers.", ["plantation", "volunteers", "field"]),
      ("Field data on land restoration", "Five years of survival-rate data across 40 sites.", ["data", "environment"])]),
    ("TechBridge Startup", "Startup", "Technology", "Mohali", "India", 30.70, 76.72, True,
     "Social-impact software studio building apps and cloud tools for non-profits.",
     [("Pilot users and community partners", "Real organisations to pilot our impact-tracking product.", ["pilot", "community", "users"]),
      ("Social impact datasets", "Anonymised datasets to train recommendation models.", ["data", "impact"])],
     [("Mobile and web app development", "Pro-bono capacity for two non-profit apps a quarter.", ["mobile", "web", "software", "developers"]),
      ("AI mentoring for students", "Weekly mentoring on machine learning projects.", ["ai", "mentoring", "students"])]),
    ("Chandigarh University CSE Dept", "College", "Education", "Mohali", "India", 30.77, 76.57, True,
     "Computer-science department with 2,000 students and an industry-linked research lab.",
     [("Real-world projects for final-year students", "Live problems from industry or NGOs for capstone projects.", ["projects", "students", "industry"]),
      ("Industry mentors and internships", "Mentors and internship slots for placement readiness.", ["mentors", "internships", "industry"])],
     [("Student volunteers for tech projects", "Teams of 4-5 students for 3-6 month projects.", ["students", "volunteers", "developers"]),
      ("Research support and lab access", "Faculty guidance, GPU lab and research assistants.", ["research", "lab", "ai"])]),
    ("HealthFirst Village Trust", "NGO", "Health", "Ludhiana", "India", 30.90, 75.85, False,
     "Mobile health camps and awareness programmes for rural communities.",
     [("Doctors for rural health camps", "Volunteer doctors and nurses, one weekend a month.", ["doctors", "health", "volunteers"]),
      ("Digital patient records system", "Simple offline-first app to record camp visits.", ["software", "records", "mobile"])],
     [("Rural community access", "Trusted relationships with 60 villages.", ["community", "outreach", "rural"]),
      ("Health camp logistics", "Venue, registration and follow-up handled end to end.", ["logistics", "health", "volunteers"])]),
    ("Punjab Skills Mission", "Government", "Skills", "Chandigarh", "India", 30.74, 76.79, True,
     "State programme training youth for jobs in technology, agriculture and green energy.",
     [("Training partners with digital curricula", "Organisations to deliver blended digital-skills courses.", ["training", "digital", "curriculum"]),
      ("Mobile app for trainee tracking", "Attendance and placement tracking for 50 training centres.", ["mobile", "app", "tracking"])],
     [("Funding for skill programmes", "Grants of up to INR 20 lakh for approved training partners.", ["funding", "grants", "training"]),
      ("Training centres and youth outreach", "Centres in 22 districts and a youth enrolment pipeline.", ["centres", "youth", "outreach"])]),
    ("AquaClean Foundation", "NGO", "Water", "Amritsar", "India", 31.63, 74.87, False,
     "Clean-water access and groundwater monitoring in border villages.",
     [("Funding for water sensors", "Low-cost IoT sensors for 30 village wells.", ["funding", "sensors", "water"]),
      ("Data analysis for groundwater trends", "Help turning sensor readings into village-level dashboards.", ["data", "analysis", "dashboards"])],
     [("Water testing and field volunteers", "Certified testers and volunteers for water-quality surveys.", ["water", "testing", "volunteers"]),
      ("Community outreach on sanitation", "Hygiene awareness sessions in schools.", ["sanitation", "outreach", "schools"])]),
    ("DataForGood Collective", "Community", "Data", "Delhi", "India", 28.61, 77.21, True,
     "Volunteer data scientists helping non-profits make decisions with data.",
     [("Non-profit projects with real datasets", "Social-sector projects needing analysis and dashboards.", ["ngo", "data", "projects"]),
      ("Cloud credits for analysis", "Hosting for analysis notebooks and dashboards.", ["cloud", "hosting", "credits"])],
     [("Data analysis and dashboards", "Cleaning, modelling and visualising data for NGOs.", ["data", "analysis", "dashboards", "machine learning"]),
      ("Volunteer data scientists", "Eight experienced volunteers, 5 hours a week each.", ["volunteers", "data", "ai"])]),
    ("SolarSathi Ltd", "Company", "Energy", "Jaipur", "India", 26.91, 75.79, True,
     "Rooftop and micro-grid solar installer with an active CSR programme.",
     [("Village partners for solar pilots", "Trusted community partners to host micro-grid pilots.", ["village", "community", "partners"]),
      ("Awareness campaigns on solar subsidies", "Campaigns that explain subsidies and financing to households.", ["awareness", "campaigns", "outreach"])],
     [("CSR funding for clean energy", "INR 50 lakh annual CSR budget for community energy projects.", ["funding", "csr", "energy"]),
      ("Solar installation and technician training", "Installation crews and an apprenticeship scheme.", ["solar", "training", "installation"])]),
    ("Bright Futures Foundation", "NGO", "Education", "Patiala", "India", 30.34, 76.39, False,
     "After-school learning centres for first-generation learners.",
     [("Volunteer teachers for maths and English", "Evening tutors for 300 children.", ["teachers", "volunteers", "education"]),
      ("Laptops and internet connectivity", "Devices and data plans for 6 learning centres.", ["laptops", "internet", "funding"])],
     [("Learning centre space and children outreach", "Six centres with trained facilitators.", ["education", "community", "children"]),
      ("Local-language learning content", "Punjabi-language worksheets and stories.", ["content", "education", "language"])]),
    ("CleanCity Municipal Corporation", "Government", "Waste", "Chandigarh", "India", 30.72, 76.77, True,
     "City body running waste segregation and recycling programmes.",
     [("Technology to track waste collection", "Route-tracking app and analytics for collection vehicles.", ["software", "tracking", "data"]),
      ("Awareness volunteers for segregation drives", "Door-to-door volunteers for 40 wards.", ["volunteers", "awareness", "waste"])],
     [("Recycling infrastructure access", "Materials recovery facilities open to pilot projects.", ["recycling", "waste", "infrastructure"]),
      ("Municipal data on waste volumes", "Ward-level waste data, updated monthly.", ["data", "waste", "city"])]),
    ("AgriConnect Cooperative", "Community", "Agriculture", "Bathinda", "India", 30.21, 74.94, False,
     "Farmer cooperative with 3,000 members focused on sustainable crop practices.",
     [("Soil-testing devices and agronomy mentors", "Affordable soil testing and expert advice for farmers.", ["soil", "mentors", "agriculture"]),
      ("Mobile app in Punjabi for crop advice", "Voice-friendly crop advisory for low-literacy users.", ["mobile", "app", "farmers"])],
     [("Farmer network for field trials", "Willing farmers for pilots of new crop and water practices.", ["farmers", "pilots", "agriculture"]),
      ("Crop yield records", "Ten years of yield and input records.", ["data", "agriculture"])]),
    ("EduSpark Technologies", "Company", "EdTech", "Bengaluru", "India", 12.97, 77.59, True,
     "Adaptive-learning platform provider with a social-impact licence programme.",
     [("Schools and NGOs for free licence programme", "Partners to roll out the platform to underserved learners.", ["schools", "ngo", "learners"]),
      ("Regional-language content creators", "Writers and teachers for Hindi and Punjabi content.", ["content", "language", "teachers"])],
     [("Free adaptive-learning licences", "10,000 learner seats for non-profits.", ["education", "software", "licences"]),
      ("Laptops donation programme", "Refurbished laptops from corporate refresh cycles.", ["laptops", "devices", "donation"])]),
]
# (org index a, org index b, title, status, score, milestones [(title, done)], metrics [(sdg,name,value,unit)], messages)
PARTNERSHIPS = [
    (0, 1, "TreeTrack mobile app", "active", 86, [("Scope and requirements", 1), ("Prototype", 1), ("Pilot with 3 sites", 0), ("Public launch", 0)],
     [(15, "Sites onboarded", 12, "sites"), (13, "Saplings tracked", 4200, "trees")], ["Kick-off done, prototype looks great!", "We will test with volunteers at the Sukhna site this weekend."]),
    (1, 2, "Student developer programme", "completed", 79, [("Select 5 students", 1), ("Deliver capstone", 1), ("Showcase demo", 1)],
     [(4, "Students mentored", 15, "students"), (9, "Apps delivered", 3, "apps")], ["Showcase went really well."]),
    (7, 10, "Solar awareness campaign", "negotiating", 64, [("Select villages", 0), ("Campaign materials", 0)], [], ["Can we share the draft budget this week?"]),
    (3, 6, "Rural health records dashboard", "proposed", 71, [], [], []),
    (8, 11, "Laptops for learning centres", "active", 82, [("Device audit", 1), ("Delivery", 0)], [(4, "Laptops delivered", 40, "devices")], ["Delivery slot confirmed for next Tuesday."]),
]


async def seed():
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == settings.admin_email).first():
            db.add(User(email=settings.admin_email, password_hash=hash_password(settings.admin_password), full_name="Platform Admin", role="admin"))
            db.commit()
        if not settings.seed_demo or db.query(Organization).count():
            return
        random.seed(7)
        orgs = []
        for i, (name, typ, sector, city, country, lat, lon, ver, desc, needs, offers) in enumerate(ORGS):
            o = Organization(name=name, type=typ, sector=sector, city=city, country=country, lat=lat, lon=lon, verified=ver, description=desc,
                             website=f"https://{name.split()[0].lower()}.example.org")
            sd = set()
            for kind, items in (("need", needs), ("offer", offers)):
                for title, d, tags in items:
                    l = Listing(kind=kind, title=title, description=d, tags=tags, sdgs=sdg.classify(f"{title} {d}", 3), created_at=now() - timedelta(days=random.randint(1, 40)))
                    l.embedding, l.embed_model = vectors.embed(l.text), ""
                    o.listings.append(l); sd |= set(l.sdgs)
            o.sdgs = sorted(sd | {17})
            db.add(o); orgs.append(o)
            slug = name.split()[0].lower()
            db.add(User(email="demo@partnerhub.dev" if i == 0 else f"{slug}@demo.dev", password_hash=hash_password("Demo@12345"), full_name=f"{name.split()[0]} Coordinator", org=o))
        db.flush()
        for a, b, title, status, score, ms, mets, msgs in PARTNERSHIPS:
            p = Partnership(org_a_id=orgs[a].id, org_b_id=orgs[b].id, title=title, status=status, match_score=score,
                            created_at=now() - timedelta(days=random.randint(3, 50)), summary=f"{orgs[a].name} and {orgs[b].name} working together on {title.lower()}.")
            p.milestones = [Milestone(title=t, done=bool(d)) for t, d in ms]
            p.metrics = [ImpactMetric(sdg=s, name=n, value=v, unit=u) for s, n, v, u in mets]
            db.add(p); db.flush()
            for j, text in enumerate(msgs):
                org = orgs[a] if j % 2 == 0 else orgs[b]
                db.add(Message(partnership_id=p.id, user_id=org.users[0].id if org.users else 1, org_id=org.id, body=text)) if org.users else None
            if status == "completed":
                db.add_all([Review(partnership_id=p.id, reviewer_org_id=orgs[a].id, reviewee_org_id=orgs[b].id, rating=5, comment="Reliable, great communication."),
                            Review(partnership_id=p.id, reviewer_org_id=orgs[b].id, reviewee_org_id=orgs[a].id, rating=4, comment="Clear goals and quick feedback.")])
        db.commit()
        db.expire_all()
        res = await llm.embed_texts(["probe"])  # if a real embedding model is configured, upgrade vectors
        if res:
            for l in db.query(Listing).all():
                out = await llm.embed_texts([l.text])
                if out:
                    l.embedding, l.embed_model = out[0][0], out[1]
            db.commit()
    finally:
        db.close()
