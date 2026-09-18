import app.db as db
from fastapi.testclient import TestClient

import app.main as main


def _client_sem_mongo():
    db.ping_db = lambda: True  # monkeypatch: nao exige mongo real
    return TestClient(main.app)


def test_healthz_ok():
    client = _client_sem_mongo()
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "degraded")


def test_docs_acessivel():
    client = _client_sem_mongo()
    r = client.get("/docs")
    assert r.status_code == 200
