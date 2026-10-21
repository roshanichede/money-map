"""Deterministic numbers. Everything the UI and the chat show is computed here, never by the model."""
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories import NEUTRAL
from .models import Transaction


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def all_transactions(session: Session) -> list[Transaction]:
    return list(session.scalars(select(Transaction).order_by(Transaction.date, Transaction.id)))


def in_month(txns: list[Transaction], month: str) -> list[Transaction]:
    return [t for t in txns if month_key(t.date) == month]


def is_spend(t: Transaction) -> bool:
    return t.category not in NEUTRAL and t.category != "Income"


def totals(txns: list[Transaction]) -> dict:
    income = sum(t.amount_pence for t in txns if t.category == "Income")
    spend = -sum(t.amount_pence for t in txns if is_spend(t))
    return {"income_pence": income, "spend_pence": spend, "net_pence": income - spend,
            "transaction_count": len(txns)}


def by_category(txns: list[Transaction]) -> list[dict]:
    agg: dict[str, dict] = defaultdict(lambda: {"spend_pence": 0, "count": 0})
    for t in txns:
        if is_spend(t):
            agg[t.category]["spend_pence"] -= t.amount_pence
            agg[t.category]["count"] += 1
    rows = [{"category": c, **v} for c, v in agg.items() if v["spend_pence"] > 0]
    return sorted(rows, key=lambda r: -r["spend_pence"])


def by_merchant(txns: list[Transaction], limit: int = 10) -> list[dict]:
    agg: dict[str, dict] = {}
    for t in txns:
        if not is_spend(t):
            continue
        row = agg.setdefault(t.merchant_key, {"merchant": t.merchant, "category": t.category,
                                               "spend_pence": 0, "count": 0})
        row["spend_pence"] -= t.amount_pence
        row["count"] += 1
    rows = [r for r in agg.values() if r["spend_pence"] > 0]
    return sorted(rows, key=lambda r: -r["spend_pence"])[:limit]


def months_overview(txns: list[Transaction]) -> list[dict]:
    months = sorted({month_key(t.date) for t in txns})
    out = []
    for m in months:
        mt = in_month(txns, m)
        first, last = min(t.date for t in mt), max(t.date for t in mt)
        out.append({"month": m, **totals(mt), "first_date": first.isoformat(), "last_date": last.isoformat()})
    return out


def categorised_rate(txns: list[Transaction]) -> float:
    if not txns:
        return 0.0
    return sum(t.category != "Other" for t in txns) / len(txns)


def compare_months(txns: list[Transaction], month: str, previous: str) -> dict:
    cur, prev = in_month(txns, month), in_month(txns, previous)
    cur_cat = {r["category"]: r for r in by_category(cur)}
    prev_cat = {r["category"]: r for r in by_category(prev)}
    changes = []
    for cat in set(cur_cat) | set(prev_cat):
        a = cur_cat.get(cat, {"spend_pence": 0, "count": 0})
        b = prev_cat.get(cat, {"spend_pence": 0, "count": 0})
        delta = a["spend_pence"] - b["spend_pence"]
        if delta == 0:
            continue
        # merchants driving the change within this category
        cur_m = {r["merchant"]: r for r in by_merchant([t for t in cur if t.category == cat], 50)}
        prev_m = {r["merchant"]: r for r in by_merchant([t for t in prev if t.category == cat], 50)}
        drivers = []
        for m in set(cur_m) | set(prev_m):
            x = cur_m.get(m, {"spend_pence": 0, "count": 0})
            y = prev_m.get(m, {"spend_pence": 0, "count": 0})
            if x["spend_pence"] != y["spend_pence"]:
                drivers.append({"merchant": m, "delta_pence": x["spend_pence"] - y["spend_pence"],
                                "this_count": x["count"], "prev_count": y["count"],
                                "this_pence": x["spend_pence"], "prev_pence": y["spend_pence"]})
        drivers.sort(key=lambda d: -abs(d["delta_pence"]))
        changes.append({"category": cat, "this_pence": a["spend_pence"], "prev_pence": b["spend_pence"],
                        "delta_pence": delta, "this_count": a["count"], "prev_count": b["count"],
                        "drivers": drivers[:3]})
    changes.sort(key=lambda c: -abs(c["delta_pence"]))
    return {"month": month, "previous": previous, "this": totals(cur), "prev": totals(prev),
            "changes": changes}


def txn_dict(t: Transaction) -> dict:
    return {"id": t.id, "date": t.date.isoformat(), "description": t.description, "merchant": t.merchant,
            "merchant_key": t.merchant_key, "type": t.txn_type, "amount_pence": t.amount_pence,
            "balance_pence": t.balance_pence, "category": t.category, "category_source": t.category_source,
            "account": t.account}
