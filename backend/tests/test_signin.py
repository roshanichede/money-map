"""Email + password accounts."""
SECRET = {"x-internal-secret": "s3cret"}


def _as(email):
    return {**SECRET, "x-user-email": email, "x-user-name": "Test"}


def test_sign_up_then_sign_in(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    r = client.post("/api/account/signup", json={"email": "Ro@Example.com ", "password": "long enough", "name": "Ro"},
                    headers=SECRET)
    assert r.status_code == 200 and r.json()["email"] == "ro@example.com"
    assert client.post("/api/account/signin", json={"email": "ro@example.com", "password": "long enough"},
                       headers=SECRET).json()["name"] == "Ro"
    bad = client.post("/api/account/signin", json={"email": "ro@example.com", "password": "wrong one"}, headers=SECRET)
    assert bad.status_code == 401
    again = client.post("/api/account/signup", json={"email": "ro@example.com", "password": "another one"}, headers=SECRET)
    assert again.status_code == 409


def test_passwords_are_hashed_and_rules_apply(client, monkeypatch, engine):
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models import Credential
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    assert client.post("/api/account/signup", json={"email": "a@b.co", "password": "short"}, headers=SECRET).status_code == 400
    assert client.post("/api/account/signup", json={"email": "nope", "password": "long enough"}, headers=SECRET).status_code == 400
    client.post("/api/account/signup", json={"email": "a@b.co", "password": "long enough"}, headers=SECRET)
    with Session(engine) as s:
        stored = s.scalar(select(Credential.password_hash))
    assert "long enough" not in stored and stored.startswith("scrypt$")


def test_browser_cannot_call_account_endpoints_directly(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    r = client.post("/api/account/signin", json={"email": "a@b.co", "password": "x" * 10})
    assert r.status_code == 403
    monkeypatch.delenv("INTERNAL_API_SECRET")
    assert client.post("/api/account/signup", json={"email": "a@b.co", "password": "x" * 10}).status_code == 403


def test_first_account_keeps_data_imported_before_login(client, monkeypatch):
    from conftest import upload
    upload(client, "lloyds_export_1.csv")
    n = client.get("/api/overview").json()["transaction_count"]
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    client.post("/api/account/signup", json={"email": "me@x.com", "password": "long enough"}, headers=SECRET)
    assert client.get("/api/overview", headers=_as("me@x.com")).json()["transaction_count"] == n
    client.post("/api/account/signup", json={"email": "two@x.com", "password": "long enough"}, headers=SECRET)
    assert client.get("/api/overview", headers=_as("two@x.com")).json()["transaction_count"] == 0


def test_repeated_wrong_passwords_are_slowed_down(client, monkeypatch):
    from app.passwords import throttle
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    client.post("/api/account/signup", json={"email": "t@x.com", "password": "long enough"}, headers=SECRET)
    for _ in range(10):
        client.post("/api/account/signin", json={"email": "t@x.com", "password": "wrong pass"}, headers=SECRET)
    r = client.post("/api/account/signin", json={"email": "t@x.com", "password": "long enough"}, headers=SECRET)
    assert r.status_code == 429
    throttle.clear("t@x.com")
