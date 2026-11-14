"""Running MoneyMap for real users: invite-only sign-up, email confirmation, password reset, deleting an account,
feedback and the owner's counts."""
import pytest

from app import links, mailer

SECRET = {"x-internal-secret": "s3cret"}


def _as(email, provider="credentials"):
    return {**SECRET, "x-user-email": email, "x-user-name": "T", "x-user-provider": provider}


@pytest.fixture()
def live(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    monkeypatch.setenv("SIGNUP_MODE", "invite")
    return client


def _signup(c, email, invite=""):
    return c.post("/api/account/signup", json={"email": email, "password": "long enough", "invite": invite},
                  headers=SECRET)


def test_first_account_needs_no_invite_then_others_do(live):
    assert _signup(live, "owner@x.com").status_code == 200
    r = _signup(live, "friend@x.com")
    assert r.status_code == 403 and "invite" in r.json()["detail"].lower()
    code = live.post("/api/owner/invites", json={"note": "Leicester society", "max_uses": 2},
                     headers=_as("owner@x.com")).json()["code"]
    assert _signup(live, "friend@x.com", code.lower()).status_code == 200   # case doesn't matter
    assert _signup(live, "friend2@x.com", code).status_code == 200
    assert _signup(live, "friend3@x.com", code).status_code == 403          # used up
    invites = live.get("/api/owner/invites", headers=_as("owner@x.com")).json()
    assert invites[0]["uses"] == 2 and invites[0]["note"] == "Leicester society"


def test_only_the_owner_sees_owner_pages(live):
    _signup(live, "owner@x.com")
    code = live.post("/api/owner/invites", json={}, headers=_as("owner@x.com")).json()["code"]
    _signup(live, "friend@x.com", code)
    assert live.get("/api/me", headers=_as("owner@x.com")).json()["is_owner"] is True
    assert live.get("/api/me", headers=_as("friend@x.com")).json()["is_owner"] is False
    for path in ("/api/owner/stats", "/api/owner/invites", "/api/owner/feedback"):
        assert live.get(path, headers=_as("friend@x.com")).status_code == 404
    stats = live.get("/api/owner/stats", headers=_as("owner@x.com")).json()
    assert stats["users"] == 2 and stats["active_this_week"] == 2 and "transactions" not in stats


def test_closed_signup(live, monkeypatch):
    _signup(live, "owner@x.com")
    monkeypatch.setenv("SIGNUP_MODE", "closed")
    assert _signup(live, "x@x.com").status_code == 403


def test_deleted_account_session_stops_working(live):
    from conftest import upload
    _signup(live, "me@x.com")
    upload(live, "lloyds_export_1.csv", headers=_as("me@x.com"))
    assert live.request("DELETE", "/api/me", json={"confirm": "nope"}, headers=_as("me@x.com")).status_code == 400
    assert live.request("DELETE", "/api/me", json={"confirm": "DELETE"}, headers=_as("me@x.com")).json()["deleted"]
    # the old browser session can't quietly recreate an empty account
    assert live.get("/api/overview", headers=_as("me@x.com")).status_code == 401
    r = live.post("/api/account/signin", json={"email": "me@x.com", "password": "long enough"}, headers=SECRET)
    assert r.status_code == 401


def test_new_google_user_needs_open_signup(live):
    _signup(live, "owner@x.com")
    assert live.get("/api/overview", headers=_as("stranger@gmail.com", "google")).status_code == 403


def test_feedback_keeps_email_only_if_allowed(live):
    _signup(live, "owner@x.com")
    live.post("/api/feedback", json={"text": "Love the UPI parsing", "can_reply": True}, headers=_as("owner@x.com"))
    live.post("/api/feedback", json={"text": "Anonymous note"}, headers=_as("owner@x.com"))
    fb = live.get("/api/owner/feedback", headers=_as("owner@x.com")).json()
    assert {f["text"]: f["reply_to"] for f in fb} == {"Love the UPI parsing": "owner@x.com", "Anonymous note": ""}


@pytest.fixture()
def with_email(live, monkeypatch):
    sent = []
    for k, v in {"SMTP_HOST": "smtp.test", "SMTP_USER": "u", "SMTP_PASSWORD": "p", "MAIL_FROM": "MoneyMap <a@b.c>"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: sent.append((to, subject, text)) or True)
    return live, sent


def _link(text, path):
    import re
    return re.search(path + r"\?token=([\w-]+)", text).group(1)


def test_email_must_be_confirmed_when_email_is_set_up(with_email):
    c, sent = with_email
    r = c.post("/api/account/signup", json={"email": "me@x.com", "password": "long enough",
                                            "origin": "https://moneymap.example"}, headers=SECRET).json()
    assert r["needs_confirming"] and sent[0][0] == "me@x.com"
    assert "https://moneymap.example/verify?token=" in sent[0][2]
    signin = lambda: c.post("/api/account/signin", json={"email": "me@x.com", "password": "long enough"}, headers=SECRET)  # noqa: E731
    assert signin().status_code == 403
    assert c.post("/api/account/verify", json={"token": "forged"}, headers=SECRET).status_code == 400
    c.post("/api/account/verify", json={"token": _link(sent[0][2], "/verify")}, headers=SECRET)
    assert signin().status_code == 200


def test_password_reset_link_works_once(with_email):
    c, sent = with_email
    c.post("/api/account/signup", json={"email": "me@x.com", "password": "long enough"}, headers=SECRET)
    c.post("/api/account/verify", json={"token": _link(sent[0][2], "/verify")}, headers=SECRET)
    assert c.post("/api/account/forgot", json={"email": "nobody@x.com"}, headers=SECRET).json() == {"ok": True}
    c.post("/api/account/forgot", json={"email": "me@x.com"}, headers=SECRET)
    token = _link(sent[-1][2], "/reset")
    assert c.post("/api/account/reset", json={"token": token, "password": "short"}, headers=SECRET).status_code == 400
    assert c.post("/api/account/reset", json={"token": token, "password": "brand new pass"}, headers=SECRET).status_code == 200
    assert c.post("/api/account/reset", json={"token": token, "password": "another new one"}, headers=SECRET).status_code == 400
    ok = c.post("/api/account/signin", json={"email": "me@x.com", "password": "brand new pass"}, headers=SECRET)
    assert ok.status_code == 200


def test_reset_unavailable_without_email(live):
    _signup(live, "me@x.com")
    assert live.post("/api/account/forgot", json={"email": "me@x.com"}, headers=SECRET).status_code == 503


def test_links_reject_other_purposes(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    t = links.make("verify", "a@b.c")
    assert links.read(t, "verify") == "a@b.c" and links.read(t, "reset") is None


def test_mail_providers(monkeypatch):
    from app import mailer
    calls = []
    monkeypatch.setattr(mailer, "_post", lambda url, headers, body: calls.append((url, headers, body)))
    monkeypatch.setenv("MAIL_FROM", "MoneyMap <hello@example.com>")
    assert not mailer.configured()
    monkeypatch.setenv("BREVO_API_KEY", "k1")
    assert mailer.send("a@b.com", "Hi", "Body")
    url, headers, body = calls[-1]
    assert "brevo" in url and headers["api-key"] == "k1"
    assert body["sender"] == {"name": "MoneyMap", "email": "hello@example.com"} and body["to"] == [{"email": "a@b.com"}]
    monkeypatch.delenv("BREVO_API_KEY")
    monkeypatch.setenv("RESEND_API_KEY", "k2")
    assert mailer.send("a@b.com", "Hi", "Body") and "resend" in calls[-1][0]
    monkeypatch.setattr(mailer, "_post", lambda *a: (_ for _ in ()).throw(OSError("down")))
    assert mailer.send("a@b.com", "Hi", "Body") is False  # a failed email never raises
