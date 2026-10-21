"""Multiple accounts, transfers between them, credit cards, users, and upgrading a v1 database."""
import shutil

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import init_db
from app.models import Account, MerchantRule, Transaction, User
from conftest import FIXTURES, SAMPLES, upload


def _accounts(client, headers=None):
    return {a["account_type"]: a for a in client.get("/api/accounts", headers=headers or {}).json()}


def test_demo_creates_three_accounts(everything):
    accts = _accounts(everything)
    assert set(accts) == {"current", "savings", "credit_card"}
    assert accts["current"]["last4"] == "5678" and accts["savings"]["last4"] == "4321"
    assert accts["current"]["balance_pence"] is not None
    assert accts["credit_card"]["balance_pence"] is None  # card exports carry no running balance


def test_pdf_joins_its_csv_account_by_number(client):
    upload(client, "lloyds_export_1.csv", "lloyds_export_2.csv")
    res = upload(client, "lloyds_statement_2026-09.pdf")[0]
    assert res["account_match"] == "matched by account number"
    assert res["rows_added"] == 0
    assert len(client.get("/api/accounts").json()) == 1


def test_full_account_number_is_never_stored(everything, engine):
    with Session(engine) as s:
        for a in s.scalars(select(Account)):
            assert "12345678" not in (a.name + a.number_hash + a.last4)


def test_card_purchases_become_spending(everything):
    card = _accounts(everything)["credit_card"]
    txns = everything.get("/api/transactions", params={"account_id": card["id"]}).json()
    purchases = [t for t in txns if "PAYMENT RECEIVED" not in t["description"]]
    assert purchases and all(t["amount_pence"] < 0 for t in purchases)


def test_reuploading_card_file_finds_same_account(everything):
    res = upload(everything, "lloyds_credit_card.csv")[0]
    assert res["rows_added"] == 0
    assert res["account_match"] == "matched to transactions already imported"
    assert len(everything.get("/api/accounts").json()) == 3


def test_transfers_between_own_accounts_are_matched(everything):
    txns = everything.get("/api/transactions", params={"month": "2026-09"}).json()
    savings_out = [t for t in txns if "TO A/C 87654321" in t["description"]]
    card_payment = [t for t in txns if t["description"] == "LLOYDS BANK PLC CREDIT CARD"]
    for t in savings_out + card_payment:
        assert t["is_transfer"] and t["category"] == "Transfers", t
    summary = everything.get("/api/summary/2026-09").json()
    cats = {c["category"] for c in summary["categories"]}
    assert "Card repayments" not in cats and "Transfers" not in cats
    assert summary["transfers_out_pence"] > 0


def test_card_repayment_counts_as_spending_until_card_uploaded(client):
    upload(client, "lloyds_export_1.csv", "lloyds_export_2.csv")
    before = client.get("/api/summary/2026-09").json()
    assert "Card repayments" in {c["category"] for c in before["categories"]}
    upload(client, "lloyds_credit_card.csv")
    after = client.get("/api/summary/2026-09").json()
    assert "Card repayments" not in {c["category"] for c in after["categories"]}
    # spending now counts the card purchases themselves instead of the repayment
    assert "Shopping" in {c["category"] for c in after["categories"]}


def test_all_accounts_total_has_no_double_counting(everything):
    accts = everything.get("/api/accounts").json()
    month = "2026-09"
    whole = everything.get(f"/api/summary/{month}").json()["spend_pence"]
    parts = sum(everything.get(f"/api/summary/{month}", params={"account_id": a["id"]}).json()["spend_pence"]
                for a in accts if everything.get(f"/api/summary/{month}", params={"account_id": a["id"]}).status_code == 200)
    assert whole == parts


def test_savings_interest_is_income_not_a_fee(everything):
    sav = _accounts(everything)["savings"]
    txns = everything.get("/api/transactions", params={"account_id": sav["id"], "q": "interest"}).json()
    assert txns and {t["category"] for t in txns} == {"Income"}


def test_explicit_new_account_for_a_file(client):
    csv = b"Date,Description,Amount\n2026-10-01,Coffee Shop,-3.50\n2026-10-02,Bakery,-2.10\n"
    r = client.post("/api/upload", files=[("files", ("monzo.csv", csv))],
                    data={"new_account_name": "Monzo", "new_account_type": "current"}).json()["results"][0]
    assert r["account"] == "Monzo"
    assert [a["name"] for a in client.get("/api/accounts").json()] == ["Monzo"]


def test_rename_and_delete_account_releases_transfers(everything):
    accts = _accounts(everything)
    r = everything.patch(f"/api/accounts/{accts['savings']['id']}", json={"name": "Rainy day pot"}).json()
    assert r["name"] == "Rainy day pot"
    everything.delete(f"/api/accounts/{accts['savings']['id']}")
    txns = everything.get("/api/transactions", params={"q": "87654321"}).json()
    assert txns and not any(t["is_transfer"] for t in txns)
    assert len(everything.get("/api/accounts").json()) == 2


def test_account_filter_rejects_other_accounts(everything):
    assert everything.get("/api/overview", params={"account_id": 9999}).status_code == 404


# ---------- users ----------

def _as(email, secret="s3cret"):
    return {"x-internal-secret": secret, "x-user-email": email, "x-user-name": "Test"}


def test_login_mode_requires_the_shared_secret(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    assert client.get("/api/overview").status_code == 401
    assert client.get("/api/overview", headers=_as("a@example.com", secret="wrong")).status_code == 401
    assert client.get("/api/overview", headers=_as("a@example.com")).status_code == 200


def test_users_only_see_their_own_data(client, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    upload(client, "lloyds_export_1.csv", headers=_as("a@example.com"))
    upload(client, "lloyds_export_1.csv", headers=_as("b@example.com"))  # same file, separate user: not a duplicate
    a = client.get("/api/overview", headers=_as("a@example.com")).json()["transaction_count"]
    b = client.get("/api/overview", headers=_as("b@example.com")).json()["transaction_count"]
    assert a == b > 0
    c = client.get("/api/overview", headers=_as("c@example.com")).json()
    assert c["transaction_count"] == 0
    txn = client.get("/api/transactions", headers=_as("a@example.com")).json()[0]
    r = client.patch(f"/api/transactions/{txn['id']}", json={"category": "Travel"}, headers=_as("c@example.com"))
    assert r.status_code == 404
    client.delete("/api/data", headers=_as("b@example.com"))
    assert client.get("/api/overview", headers=_as("a@example.com")).json()["transaction_count"] == a


def test_first_google_user_inherits_local_data(client, monkeypatch, engine):
    upload(client, "lloyds_export_1.csv")  # local mode
    local_count = client.get("/api/overview").json()["transaction_count"]
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    assert client.get("/api/overview", headers=_as("me@gmail.com")).json()["transaction_count"] == local_count
    assert client.get("/api/overview", headers=_as("friend@gmail.com")).json()["transaction_count"] == 0
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(User)) == 2


# ---------- upgrading a v1 database ----------

def test_v1_database_upgrades_without_losing_anything(tmp_path):
    db = tmp_path / "moneymap.db"
    shutil.copy(FIXTURES / "v1.db", db)
    engine = create_engine(f"sqlite:///{db}")
    init_db(engine)
    assert (tmp_path / "moneymap.v1-backup.db").exists()
    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(Transaction)) == 251
        assert s.scalar(select(func.count()).select_from(Account)) == 1
        assert s.scalar(select(func.count()).select_from(MerchantRule)) == 1
        assert s.scalar(select(func.count()).select_from(Transaction).where(Transaction.category_source == "manual")) == 1
        # migrated duplicate keys match what the importer would compute, so re-uploads are still skipped
        from app.importer import dedupe_keys
        from app.parsers import ParsedTxn, ParseResult
        for upload_id in s.scalars(select(Transaction.upload_id).distinct()):
            rows = list(s.scalars(select(Transaction).where(Transaction.upload_id == upload_id).order_by(Transaction.id)))
            result = ParseResult("lloyds_csv", [ParsedTxn(r.date, r.description, r.amount_pence, r.balance_pence)
                                                for r in rows])
            assert dedupe_keys(result, rows[0].account_id) == [r.dedupe_key for r in rows]
    init_db(engine)  # starting again is a no-op
