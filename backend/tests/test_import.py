from datetime import date

import pytest

from app.parsers import ParseError, parse_statement
from app.parsers.common import parse_money
from conftest import SAMPLES, upload


def test_parse_money():
    assert parse_money("1,234.56") == 123456
    assert parse_money("£12.30") == 1230
    assert parse_money("(5.00)") == -500
    assert parse_money("10.00DR") == -1000
    assert parse_money("") is None


def test_lloyds_csv_is_chronological_with_signed_amounts():
    r = parse_statement("x.csv", (SAMPLES / "lloyds_export_1.csv").read_bytes())
    assert r.source_format == "lloyds_csv"
    assert r.transactions[0].date == date(2026, 5, 1)
    assert r.transactions[-1].date >= r.transactions[0].date
    rent = r.transactions[0]
    assert rent.amount_pence == -85000 and rent.txn_type == "SO"
    assert any(t.amount_pence > 0 for t in r.transactions)  # salary


def test_generic_csv_single_amount_column():
    csv = b"Date,Name,Amount\n2026-10-01,Coffee Shop,-3.50\n2026-10-02,Refund,10.00\n"
    r = parse_statement("monzo.csv", csv)
    assert r.source_format == "generic_csv"
    assert [t.amount_pence for t in r.transactions] == [-350, 1000]


def test_unreadable_csv_gives_clear_error():
    with pytest.raises(ParseError, match="Couldn't find date"):
        parse_statement("x.csv", b"foo,bar\n1,2\n")


def test_pdf_statement_parses_and_rejoins_wrapped_descriptions():
    r = parse_statement("s.pdf", (SAMPLES / "lloyds_statement_2026-09.pdf").read_bytes())
    assert r.source_format == "pdf"
    assert r.opening_balance_pence is not None
    assert all(t.date.month == 9 for t in r.transactions)
    assert any(t.description == "TFL TRAVEL CH TFL.GOV.UK/CP CD 4821" for t in r.transactions)


def test_overlapping_exports_are_deduplicated(client):
    res = upload(client, "lloyds_export_1.csv", "lloyds_export_2.csv")
    total_rows = res[0]["rows_read"] + res[1]["rows_read"]
    added = res[0]["rows_added"] + res[1]["rows_added"]
    assert res[1]["duplicates_skipped"] > 0
    assert added == total_rows - res[1]["duplicates_skipped"]
    assert client.get("/api/overview").json()["transaction_count"] == added
    again = upload(client, "lloyds_export_2.csv")[0]
    assert again["rows_added"] == 0


def test_pdf_after_csv_adds_nothing(loaded):
    before = loaded.get("/api/overview").json()["transaction_count"]
    res = upload(loaded, "lloyds_statement_2026-09.pdf")[0]
    assert res["rows_added"] == 0, res
    assert loaded.get("/api/overview").json()["transaction_count"] == before


def test_every_import_reconciles(client):
    for res in upload(client, "lloyds_export_1.csv", "lloyds_export_2.csv", "lloyds_statement_2026-09.pdf"):
        assert res["reconciled"] == "ok", res


def test_missing_row_is_flagged(client):
    lines = (SAMPLES / "lloyds_export_2.csv").read_bytes().splitlines()
    broken = b"\n".join(lines[:10] + lines[11:])  # drop one transaction
    r = client.post("/api/upload", files=[("files", ("broken.csv", broken))]).json()["results"][0]
    assert r["reconciled"] == "mismatch"
