def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_auth_required(client):
    assert client.get("/api/matches").status_code == 401


def test_register_validation_and_login(client):
    bad = {"email": "nope", "password": "longenough1", "full_name": "Test User", "org_name": "Test Org"}
    assert client.post("/api/auth/register", json=bad).status_code == 422
    ok = {**bad, "email": "new@org.dev", "org_name": "Fresh Org", "org_type": "Startup"}
    r = client.post("/api/auth/register", json=ok)
    assert r.status_code == 200 and r.json()["user"]["org"]["name"] == "Fresh Org"
    assert client.post("/api/auth/register", json=ok).status_code == 409
    assert client.post("/api/auth/login", json={"email": "new@org.dev", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "new@org.dev", "password": "longenough1"}).status_code == 200


def test_matches_are_ranked_and_explainable(client, demo):
    m = client.get("/api/matches", headers=demo).json()
    assert m and m == sorted(m, key=lambda x: -x["score"])
    assert m[0]["org"]["name"] == "TechBridge Startup"
    assert set(m[0]["breakdown"]) == {"semantic", "sdg", "geo", "trust", "reciprocity"}
    assert m[0]["they_give"] and m[0]["you_give"]


def test_semantic_search(client, demo):
    r = client.get("/api/listings", params={"q": "android developers", "kind": "offer"}, headers=demo).json()
    assert r and "app" in (r[0]["title"] + r[0]["description"]).lower()


def test_listing_crud_and_isolation(client, demo):
    r = client.post("/api/listings", json={"kind": "need", "title": "Legal advice on NGO registration", "tags": ["legal"]}, headers=demo)
    assert r.status_code == 200 and r.json()["sdgs"]
    lid = r.json()["id"]
    other = client.post("/api/auth/login", json={"email": "techbridge@demo.dev", "password": "Demo@12345"}).json()["token"]
    assert client.delete(f"/api/listings/{lid}", headers={"Authorization": "Bearer " + other}).status_code == 404
    assert client.delete(f"/api/listings/{lid}", headers=demo).status_code == 200


def test_partnership_lifecycle_and_permissions(client, demo):
    orgs = {o["name"]: o["id"] for o in client.get("/api/orgs", headers=demo).json()}
    r = client.post("/api/partnerships", headers=demo, json={"org_id": orgs["SolarSathi Ltd"], "title": "Solar for villages", "milestones": ["Kick-off", "Pilot"]})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert client.post("/api/partnerships", headers=demo, json={"org_id": orgs["SolarSathi Ltd"], "title": "Duplicate"}).status_code == 409
    # initiator cannot accept their own proposal
    assert client.post(f"/api/partnerships/{pid}/status", headers=demo, json={"status": "negotiating"}).status_code == 403
    rcv = client.post("/api/auth/login", json={"email": "solarsathi@demo.dev", "password": "Demo@12345"}).json()["token"]
    rh = {"Authorization": "Bearer " + rcv}
    assert client.post(f"/api/partnerships/{pid}/status", headers=rh, json={"status": "negotiating"}).status_code == 200
    assert client.post(f"/api/partnerships/{pid}/status", headers=rh, json={"status": "completed"}).status_code == 422
    assert client.post(f"/api/partnerships/{pid}/status", headers=rh, json={"status": "active"}).status_code == 200
    d = client.post(f"/api/partnerships/{pid}/milestones/{client.get(f'/api/partnerships/{pid}', headers=demo).json()['milestones'][0]['id']}/toggle", headers=demo).json()
    assert d["progress"] == 50
    assert client.post(f"/api/partnerships/{pid}/metrics", headers=demo, json={"sdg": 7, "name": "Homes powered", "value": 120, "unit": "homes"}).status_code == 200
    assert client.post(f"/api/partnerships/{pid}/messages", headers=rh, json={"body": "Hello!"}).status_code == 200
    assert client.post(f"/api/partnerships/{pid}/review", headers=demo, json={"rating": 5}).status_code == 422  # not completed yet
    client.post(f"/api/partnerships/{pid}/status", headers=demo, json={"status": "completed"})
    assert client.post(f"/api/partnerships/{pid}/review", headers=demo, json={"rating": 5, "comment": "Great"}).status_code == 200
    assert client.post(f"/api/partnerships/{pid}/review", headers=demo, json={"rating": 5}).status_code == 409
    outsider = client.post("/api/auth/login", json={"email": "aquaclean@demo.dev", "password": "Demo@12345"}).json()["token"]
    assert client.get(f"/api/partnerships/{pid}", headers={"Authorization": "Bearer " + outsider}).status_code == 404


def test_notifications_created(client, demo):
    rcv = client.post("/api/auth/login", json={"email": "solarsathi@demo.dev", "password": "Demo@12345"}).json()["token"]
    n = client.get("/api/notifications", headers={"Authorization": "Bearer " + rcv}).json()
    assert any("proposed a partnership" in x["text"] for x in n)


def test_ai_fallbacks_work_without_model(client, demo):
    orgs = {o["name"]: o["id"] for o in client.get("/api/orgs", headers=demo).json()}
    for ep in ("explain", "outreach", "plan"):
        r = client.post(f"/api/ai/{ep}", headers=demo, json={"org_id": orgs["TechBridge Startup"]}).json()
        assert r["ai"] is False and (r.get("text") or r.get("milestones"))
    assert client.post("/api/ai/tag", headers=demo, json={"text": "solar energy for villages"}).json()["sdgs"]
    assert client.post("/api/ai/copilot", headers=demo, json={"message": "Who should I talk to?"}).json()["text"]


def test_admin_only(client, demo, admin):
    assert client.get("/api/admin/overview", headers=demo).status_code == 403
    assert client.get("/api/admin/overview", headers=admin).status_code == 200
    oid = client.get("/api/admin/overview", headers=admin).json()["pending"][0]["id"]
    assert client.post(f"/api/orgs/{oid}/verify", headers=admin).json()["verified"] is True


def test_analytics_and_export(client, demo):
    o = client.get("/api/analytics/overview", headers=demo).json()
    assert o["orgs"] >= 12 and o["gaps"] is not None and len(o["weekly"]) == 8
    assert client.get("/api/analytics/impact", headers=demo).json()["partnerships"] >= 1
    assert client.get("/api/export/partnerships.csv", headers=demo).text.startswith("id,title")


def test_pact_product_shell_is_served(client):
    page = client.get('/')
    assert page.status_code == 200
    assert 'PACT — Partnership Intelligence' in page.text
    assert '/assets/styles.css' in page.text
    assert '/assets/app.js' in page.text


def test_pact_frontend_assets_are_served(client):
    css = client.get('/assets/styles.css')
    js = client.get('/assets/app.js')
    assert css.status_code == 200 and '.app-frame' in css.text
    assert js.status_code == 200 and 'Partner intelligence' in js.text


def test_impact_evidence_review_requires_admin_and_evidence(client, demo, admin):
    orgs = {o["name"]: o["id"] for o in client.get("/api/orgs", headers=demo).json()}
    created = client.post("/api/partnerships", headers=demo, json={
        "org_id": orgs["SolarSathi Ltd"], "title": "Evidence review pilot", "milestones": ["Pilot"]
    })
    assert created.status_code == 200
    pid = created.json()["id"]
    metric = client.post(f"/api/partnerships/{pid}/metrics", headers=demo, json={
        "sdg": 7, "name": "Homes reached", "value": 12, "unit": "homes",
        "evidence_url": "https://example.org/impact-report"
    })
    assert metric.status_code == 200
    mid = metric.json()["metrics"][0]["id"]
    assert metric.json()["metrics"][0]["verification_status"] == "pending_review"
    assert client.post(f"/api/admin/impact/{mid}/review", headers=demo,
                       json={"status": "verified", "note": "reviewed"}).status_code == 403
    verified = client.post(f"/api/admin/impact/{mid}/review", headers=admin,
                           json={"status": "verified", "note": "Evidence checked"})
    assert verified.status_code == 200
    detail = client.get(f"/api/partnerships/{pid}", headers=demo).json()
    assert detail["metrics"][0]["verification_status"] == "verified"
