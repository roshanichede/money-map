from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_session, init_db
from app.main import app

SAMPLES = Path(__file__).parent.parent / "sample_data"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(eng)
    return eng


@pytest.fixture()
def client(monkeypatch, engine):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("INTERNAL_API_SECRET", raising=False)
    monkeypatch.setattr("app.main.init_db", lambda: None)  # tests use the in-memory engine above
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


def upload(client, *names, headers=None, data=None):
    files = [("files", (n, (SAMPLES / n).read_bytes())) for n in names]
    r = client.post("/api/upload", files=files, headers=headers or {}, data=data or {})
    assert r.status_code == 200, r.text
    return r.json()["results"]


@pytest.fixture()
def loaded(client):
    """Current account only (two overlapping exports)."""
    upload(client, "lloyds_export_1.csv", "lloyds_export_2.csv")
    return client


@pytest.fixture()
def everything(client):
    """Current account, its PDF, savings and credit card."""
    r = client.post("/api/demo")
    assert r.status_code == 200, r.text
    return client
