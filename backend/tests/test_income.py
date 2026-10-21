"""Money coming in: salary vs other income vs friends paying you back, earnings, highlights, upgrading old data."""
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categories import categorise, split_code
from app.income import detect_salary, upgrade_existing_data
from app.merchants import normalise
from app.models import Account, AppMeta, MerchantRule, Transaction, Upload, User


def _cat(desc, pence, code=""):
    key, _ = normalise(desc)
    return categorise(desc, key, code, pence)


@pytest.mark.parametrize("desc, pence, expected", [
    ("ACME DIGITAL LTD SALARY", 248500, "Salary"),
    ("J SMITH DINNER SPLIT", 1500, "Eating out"),     # a friend's share of dinner
    ("PRIYA SHAH CAB", 1200, "Transport"),            # a friend's share of a cab you booked
    ("RAHUL K", 5000, "From people"),                 # a person, no note: neither earnings nor spending
    ("FPI A KHAN MY SHARE OF RENT ••0503", 35300, "Rent & housing"),
    ("FPI B ROY 1STDAYGROCERY, ••3001", 5030, "Groceries"),    # note glued to other text
    ("FPI C DAS 17MAY25 UTILITY BILL ••3531", 2200, "Bills & utilities"),
    ("BGC PRIMARK STORES LTD", 76800, "Other income"),         # payroll code: pay, not a Primark refund
    ("BGC NORTHGATE OPERATIONS LIM", 13200, "Other income"),   # "LIM" = a truncated LIMITED
    ("FPI JANE DOE SELF TRANSFER REV••8714", 60000, "Transfers"),
    ("EARLY STAGE LTD", 60000, "Other income"),       # a company, one-off: freelance or similar
    ("TESCO STORES REFUND", 500, "Groceries"),        # a shop refund reduces that category
    ("INTEREST (GROSS)", 1915, "Other income"),
])
def test_money_in_is_sorted_by_who_paid(desc, pence, expected):
    assert _cat(desc, pence) == expected


def test_statement_codes_are_not_part_of_the_name():
    assert split_code("DD THE GYM LTD", "")[1] == "THE GYM LTD"
    assert normalise("DD THE GYM LTD") == normalise("THE GYM LTD")
    assert _cat("DD THE GYM LTD", -1899, "DD") == "Health & fitness"


def _setup(engine):
    s = Session(engine)
    u = User(email="t@example.com")
    s.add(u)
    s.flush()
    a = Account(user_id=u.id, name="Current")
    s.add(a)
    s.flush()
    up = Upload(user_id=u.id, account_id=a.id, filename="x.csv", source_format="generic_csv")
    s.add(up)
    s.flush()
    return s, u, a, up


def _txn(s, u, a, up, d, desc, pence, category, source="rule", key=None):
    k, name = normalise(desc)
    t = Transaction(user_id=u.id, account_id=a.id, upload_id=up.id, date=d, description=desc, merchant=name,
                    merchant_key=key or k, amount_pence=pence, category=category, category_source=source,
                    dedupe_key=f"{d}{desc}{pence}")
    s.add(t)
    return t


def test_regular_company_payments_become_salary(engine):
    s, u, a, up = _setup(engine)
    pay = [_txn(s, u, a, up, date(2026, m, 28), "BRIGHT WIDGETS LTD", 210000 + m * 500, "Other income")
           for m in (7, 8, 9)]
    one_off = _txn(s, u, a, up, date(2026, 9, 3), "SIDE GIG LTD", 40000, "Other income")
    friend = [_txn(s, u, a, up, date(2026, m, 1), "ANNA LEE", 45000, "From people") for m in (8, 9)]
    s.flush()
    detect_salary(s, u.id)
    assert {t.category for t in pay} == {"Salary"}
    assert one_off.category == "Other income"
    assert {t.category for t in friend} == {"From people"}  # people are never salary


def test_part_time_payroll_with_varying_amounts_is_salary(engine):
    s, u, a, up = _setup(engine)
    shifts = [_txn(s, u, a, up, date(2026, m, d), "BGC PRIMARK STORES LTD", p, "Other income")
              for m, d, p in ((6, 14, 1000), (7, 12, 76800), (8, 9, 23150))]
    once = _txn(s, u, a, up, date(2026, 8, 2), "BGC ONE DAY EVENTS", 9000, "Other income")
    s.flush()
    detect_salary(s, u.id)
    assert {t.category for t in shifts} == {"Salary"}
    assert once.category == "Other income"  # only paid once so far


def test_old_income_bucket_is_resorted_once(engine):
    s, u, a, up = _setup(engine)
    s.query(AppMeta).delete()  # pretend this database was sorted by the old rules
    salary = _txn(s, u, a, up, date(2026, 9, 28), "ACME DIGITAL LTD SALARY", 248500, "Income")
    friend = _txn(s, u, a, up, date(2026, 9, 12), "PRIYA SHAH CAB", 1200, "Income")
    mine = _txn(s, u, a, up, date(2026, 9, 14), "MUM", 10000, "Income", source="manual")
    gym = _txn(s, u, a, up, date(2026, 9, 2), "DD THE GYM LTD", -1899, "Health & fitness", source="learned",
               key="DD THE GYM LTD")
    s.add(MerchantRule(user_id=u.id, merchant_key="DD THE GYM LTD", category="Health & fitness"))
    s.commit()
    upgrade_existing_data(s)
    assert salary.category == "Salary" and friend.category == "Transport"
    assert mine.category == "Other income"  # the user's own choice is kept, just renamed
    rule = s.scalar(select(MerchantRule))
    assert rule.merchant_key == gym.merchant_key == normalise("THE GYM LTD")[0]  # future gym payments still match
    assert s.get(AppMeta, "rules_version").value == "2"
    friend.category = "Gifts & charity"
    s.commit()
    upgrade_existing_data(s)  # already upgraded: nothing changes
    assert friend.category == "Gifts & charity"


def test_paid_back_reduces_spending_and_is_not_earnings(loaded):
    tx = loaded.get("/api/transactions", params={"q": "dinner split"}).json()
    assert tx and all(t["kind"] == "paid_back" and t["category"] == "Eating out" for t in tx)
    month = tx[0]["date"][:7]
    s = loaded.get(f"/api/summary/{month}").json()
    assert s["salary_pence"] == 248500 and s["income_pence"] == s["salary_pence"] + s["other_income_pence"]
    assert s["paid_back_pence"] == sum(t["amount_pence"] for t in tx if t["date"].startswith(month))
    assert any(h["kind"] == "paid_back" and "not counted as earnings" in h["text"] for h in s["highlights"])


def test_highlights_are_plain_sentences(loaded):
    hs = loaded.get("/api/summary/2026-09").json()["highlights"]
    kinds = [h["kind"] for h in hs]
    assert kinds[0] == "top" and "salary" in kinds
    assert all(h["text"].endswith(".") and "%" not in h["text"].split("about")[0] for h in hs)


def test_earnings_this_year_and_by_source(everything):
    e = everything.get("/api/earnings").json()
    assert e["year"] == 2026
    assert e["this_year"]["income_pence"] == sum(m["salary_pence"] + m["other_income_pence"] for m in e["months"]
                                                 if m["month"].startswith("2026"))
    top = e["sources"][0]
    assert top["kind"] == "salary" and top["count"] >= 2
    assert not any(s["kind"] == "transfer" for s in e["sources"])
    salary_days = [t["date"][8:] for t in everything.get("/api/transactions", params={"q": "salary"}).json()]
    assert f"{e['usual_salary_day']:02d}" in salary_days


def test_card_refunds_are_refunds_not_people():
    from app.categories import money_in_kind
    assert money_in_kind("Shopping", 1299, "DEB Temu.com CD 9415", False) == "refund"
    assert money_in_kind("Transport", 900, "FPI P KUMAR UBER HOME ••5749", False) == "paid_back"
