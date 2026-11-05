import os, tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["LLM_MODEL"] = ""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def demo(client):
    r = client.post("/api/auth/login", json={"email": "demo@partnerhub.dev", "password": "Demo@12345"})
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture(scope="session")
def admin(client):
    r = client.post("/api/auth/login", json={"email": "admin@partnerhub.dev", "password": "Admin@12345"})
    return {"Authorization": "Bearer " + r.json()["token"]}
