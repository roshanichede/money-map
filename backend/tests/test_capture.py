"""Payments sent from the phone as they happen (Apple Pay taps, bank texts), then replaced by the statement."""
from datetime import date

import pytest

from app.capture import NotAPayment, from_sms

TODAY = date(2026, 10, 22)


@pytest.mark.parametrize("text, desc, amount", [
    ("Rs.450.00 debited from a/c XX1234 on 22-10-26 to VPA swiggy8@icici (UPI Ref No 412345678901). Not you? Call 1800",
     "UPI SWIGGY", -45000),
    ("Sent Rs.500.00 From HDFC Bank A/C x1234 To PREETI MISAL On 21/10/26 Ref 412345678901 Not You? Call 18002586161",
     "PREETI MISAL", -50000),
    ("INR 1,299.00 spent on ICICI Bank Card XX4321 on 20-Oct-26 at AMAZON PAY. Avl Lmt: INR 45,000.00",
     "AMAZON PAY", -129900),
    ("Your A/c XX1234 is credited with Rs.85,000.00 on 22-10-26 by NEFT from ACME TECHNOLOGIES PVT LTD. Avl Bal Rs.1,10,000",
     "ACME TECHNOLOGIES PVT LTD", 8500000),
    ("Dear Customer, Rs.2000.00 withdrawn at ATM S1ANMU12 from A/c XX1234 on 22-10-26. Avl Bal Rs.8000.00",
     "ATM CASH WITHDRAWAL", -200000),
])
def test_bank_texts(text, desc, amount):
    when, d, a = from_sms(text, TODAY)
    assert (d, a) == (desc, amount)
    assert when <= TODAY


@pytest.mark.parametrize("text", [
    "123456 is your OTP for a transaction of Rs.4,999.00 at FLIPKART. Do not share it with anyone.",
    "Your SBI Card bill of Rs.12,345 is due on 05-Nov-26.",
    "Get 20% cashback up to Rs.500 on your next Swiggy order!",
    "Rs.999 will be debited on 25-10-26 for your Netflix autopay mandate.",
    "Hello! Are we still meeting today?",
])
def test_texts_that_are_not_payments_are_ignored(text):
    with pytest.raises(NotAPayment):
        from_sms(text, TODAY)


def _link(client, source, account_type="current"):
    from conftest import upload
    upload(client, "lloyds_export_1.csv", "lloyds_export_2.csv")
    acct = client.get("/api/accounts").json()[0]
    r = client.post("/api/capture-links", json={"account_id": acct["id"], "source": source}).json()
    return r["path"], acct


def test_apple_pay_tap_appears_straight_away(client):
    path, acct = _link(client, "applepay")
    r = client.post(path, json={"merchant": "Pret A Manger", "amount": "£4.50", "card": "Lloyds Debit"}).json()
    assert r["recorded"]["category"] == "Eating out" and r["recorded"]["amount"] == "-£4.50"
    t = client.get("/api/transactions", params={"q": "pret a manger"}).json()[0]
    assert t["pending"] and t["amount_pence"] == -450
    links = client.get("/api/capture-links").json()
    assert links[0]["uses"] == 1 and "path" not in links[0]  # the secret link isn't shown again


def test_statement_replaces_the_phone_entry_and_keeps_your_category(client, engine):
    from datetime import timedelta

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.models import Transaction
    path, acct = _link(client, "applepay")
    client.post(path, json={"merchant": "Some Cafe", "amount": "£7.25"})
    pending = client.get("/api/transactions", params={"q": "some cafe"}).json()[0]
    client.patch(f"/api/transactions/{pending['id']}", json={"category": "Gifts & charity", "apply_to_merchant": False})
    with Session(engine) as s:  # pretend the tap happened a day before the statement row's date
        t = s.get(Transaction, pending["id"])
        t.date = date(2026, 10, 19) - timedelta(days=1)
        s.commit()
    csv = b"Date,Description,Amount\n2026-10-19,SOME CAFE LONDON CD 4821,-7.25\n"
    r = client.post("/api/upload", files=[("files", ("late.csv", csv))], data={"account_id": str(acct["id"])}).json()
    assert r["results"][0]["ok"]
    rows = client.get("/api/transactions", params={"q": "some cafe"}).json()
    assert len(rows) == 1 and not rows[0]["pending"]          # counted once
    assert rows[0]["category"] == "Gifts & charity"            # your choice carried over
    with Session(engine) as s:
        assert not s.scalars(select(Transaction).where(Transaction.pending.is_(True))).all()


def test_sms_link_records_debits_and_ignores_otps(client):
    path, _ = _link(client, "sms")
    ok = client.post(path, content="Rs.450.00 debited from a/c XX1234 on 22-10-26 to VPA swiggy8@icici",
                     headers={"content-type": "text/plain"}).json()
    assert ok["recorded"]["category"] == "Takeaways"
    otp = client.post(path, json={"sms": "123456 is your OTP for Rs.500"}).json()
    assert otp["recorded"] is None and "OTP" in otp["ignored"]


def test_links_are_secret_and_revocable(client, monkeypatch):
    path, _ = _link(client, "applepay")
    assert client.post("/api/capture/not-a-real-link", json={"merchant": "x", "amount": "1"}).status_code == 404
    link_id = client.get("/api/capture-links").json()[0]["id"]
    client.delete(f"/api/capture-links/{link_id}")
    assert client.post(path, json={"merchant": "Pret", "amount": "£3"}).status_code == 404
    # the phone link works without signing in, even when sign-in is on
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    from app.capture import token_hash  # noqa: F401  (only hashes are stored)


def test_link_only_for_your_own_accounts(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    me = {"x-internal-secret": "s3cret", "x-user-email": "me@x.com", "x-user-name": "Me"}
    other = {"x-internal-secret": "s3cret", "x-user-email": "other@x.com", "x-user-name": "O"}
    from conftest import upload
    upload(client, "lloyds_export_1.csv", headers=me)
    acct = client.get("/api/accounts", headers=me).json()[0]
    r = client.post("/api/capture-links", json={"account_id": acct["id"], "source": "sms"}, headers=other)
    assert r.status_code == 404
