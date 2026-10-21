from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_session, init_db
from app.main import app

SAMPLES = Path(__file__).parent.parent / "sample_data"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def upload(client, *names):
    files = [("files", (n, (SAMPLES / n).read_bytes())) for n in names]
    r = client.post("/api/upload", files=files)
    assert r.status_code == 200, r.text
    return r.json()["results"]


@pytest.fixture()
def loaded(client):
    upload(client, "lloyds_export_1.csv", "lloyds_export_2.csv")
    return client
