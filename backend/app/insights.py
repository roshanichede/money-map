"""Deterministic numbers. Everything the UI and the chat show is computed here, never by the model."""
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

import re

from .categories import INCOME_CATEGORIES, NEUTRAL, PAID_BACK_NOTES, SALARY_RE, money_in_kind
from .models import Transaction


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def all_transactions(session: Session, user_id: int, account_id: int | None = None) -> list[Transaction]:
    q = select(Transaction).where(Transaction.user_id == user_id)
    if account_id is not None:
        q = q.where(Transaction.account_id == account_id)
    return list(session.scalars(q.order_by(Transaction.date, Transaction.id)))


def in_month(txns: list[Transaction], month: str) -> list[Transaction]:
    return [t for t in txns if month_key(t.date) == month]


def is_spend(t: Transaction) -> bool:
    """Spending categories. Money paid back by friends and shop refunds sit here as positive amounts,
    so they reduce spending instead of counting as income."""
    return t.category not in NEUTRAL and t.category not in INCOME_CATEGORIES


def kind(t: Transaction) -> str:
    if t.amount_pence < 0:
        return "transfer" if (t.transfer_pair_id is not None or t.category == "Transfers") else "spend"
    return money_in_kind(t.category, t.amount_pence, t.description, t.transfer_pair_id is not None, t.txn_type) or "spend"


def totals(txns: list[Transaction]) -> dict:
    salary = sum(t.amount_pence for t in txns if t.category == "Salary")
    other = sum(t.amount_pence for t in txns if t.category == "Other income")
    paid_back = sum(t.amount_pence for t in txns if t.amount_pence > 0 and is_spend(t) and kind(t) == "paid_back")
    refunds = sum(t.amount_pence for t in txns if t.amount_pence > 0 and is_spend(t) and kind(t) == "refund")
    from_people = sum(t.amount_pence for t in txns if t.category == "From people" and t.amount_pence > 0)
    spend = -sum(t.amount_pence for t in txns if is_spend(t))
    income = salary + other
    return {"income_pence": income, "salary_pence": salary, "other_income_pence": other,
            "paid_back_pence": paid_back, "from_people_pence": from_people, "refunds_pence": refunds,
            "spend_pence": spend,
            "net_pence": income - spend, "transaction_count": len(txns)}


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
            "account_id": t.account_id, "is_transfer": t.transfer_pair_id is not None, "kind": kind(t)}


# ---------- earnings ----------

def earnings(txns: list[Transaction]) -> dict:
    """What came in: this year, all time, by month and by who paid you."""
    if not txns:
        return {"year": None, "this_year": None, "all_time": None, "months": [], "sources": []}
    year = max(t.date for t in txns).year
    in_year = [t for t in txns if t.date.year == year]
    ty, at = totals(in_year), totals(txns)
    months = []
    for m in sorted({month_key(t.date) for t in txns}):
        mt = totals(in_month(txns, m))
        months.append({"month": m, "salary_pence": mt["salary_pence"], "other_income_pence": mt["other_income_pence"],
                       "paid_back_pence": mt["paid_back_pence"], "from_people_pence": mt["from_people_pence"]})
    sources: dict[str, dict] = {}
    for t in txns:
        k = kind(t)
        if t.amount_pence <= 0 or k in ("transfer", "refund", "spend"):
            continue
        name = payer_name(t.merchant)
        if k in ("paid_back", "from_person"):  # a person: "ANNA LEE" -> "Anna Lee"
            name = " ".join(w if len(w) == 1 else w.capitalize() for w in name.split())
        row = sources.setdefault(f"{k}|{name.upper()}", {"name": name, "kind": k, "total_pence": 0, "count": 0,
                                                  "last_date": t.date.isoformat(), "category": t.category})
        row["total_pence"] += t.amount_pence
        row["count"] += 1
        row["last_date"] = max(row["last_date"], t.date.isoformat())
    first = min(t.date for t in txns)
    salary_days = [t.date.day for t in txns if t.category == "Salary"]
    return {
        "year": year,
        "this_year": {"income_pence": ty["income_pence"], "salary_pence": ty["salary_pence"],
                      "other_income_pence": ty["other_income_pence"], "paid_back_pence": ty["paid_back_pence"],
                      "from_people_pence": ty["from_people_pence"],
                      "since": min(t.date for t in in_year).isoformat()},
        "all_time": {"income_pence": at["income_pence"], "since": first.isoformat()},
        "months": months,
        "sources": sorted(sources.values(), key=lambda r: -r["total_pence"])[:8],
        "usual_salary_day": sorted(salary_days)[len(salary_days) // 2] if salary_days else None,
    }


# ---------- highlights: the few things worth knowing this month, in plain words ----------

_NOTE_WORDS = re.compile(r"\s+(?:" + SALARY_RE.pattern + "|" + "|".join(PAID_BACK_NOTES.values())
                         + r"|SPLIT|SHARE|THANKS|INV(?:OICE)?|REF|\d+)\b.*$", re.I)


_PAYER_NOISE = re.compile(r"\s*(?:••.*|\bREV\b.*|\b(?:MY SHARE|SHARE OF|SENT FROM|FROM|PAYMENT|TO|FOR)\b.*)$", re.I)


def payer_name(merchant: str) -> str:
    """'J Smith Dinner Split' -> 'J Smith', 'Acme Digital LTD Salary' -> 'Acme Digital Ltd',
    'V Khatode MY Share' -> 'V Khatode', 'M Lande Rent ••' -> 'M Lande'."""
    name = merchant
    for _ in range(3):
        name = _PAYER_NOISE.sub("", _NOTE_WORDS.sub("", name)).strip() or name
    name = re.sub(r"\bLIM\b|\bLTD\b", "Ltd", name)
    return name


def _pounds(pence: int) -> str:
    return f"£{round(abs(pence) / 100):,}"


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def highlights(txns: list[Transaction], month: str, comparison: dict | None, unfinished: bool) -> list[dict]:
    mt = in_month(txns, month)
    tt = totals(mt)
    cats = by_category(mt)
    out: list[dict] = []
    spend = tt["spend_pence"]

    if cats and spend > 0:
        top = cats[0]
        share = round(100 * top["spend_pence"] / spend)
        out.append({"kind": "top", "category": top["category"],
                    "text": f"Your biggest cost was {_label(top['category'])}: {_pounds(top['spend_pence'])}, "
                            f"about {share}% of what you spent."})

    if comparison:
        ups = [c for c in comparison["changes"] if c["delta_pence"] >= 2000 and c["category"] != "Other"]
        if ups:
            c = max(ups, key=lambda x: x["delta_pence"])
            d = c["drivers"][0] if c["drivers"] else None
            why = ""
            if d and d["delta_pence"] > 0:
                why = (f", mostly {d['merchant']}" if d["prev_count"] else f", mostly {d['merchant']} (new this month)")
            lead = "already " if unfinished else ""
            out.append({"kind": "up", "category": c["category"],
                        "text": f"{_label(c['category']).capitalize()} is {lead}up {_pounds(c['delta_pence'])} on last month{why}."})
        downs = [c for c in comparison["changes"] if c["delta_pence"] <= -2000 and c["category"] != "Other"]
        if downs and not unfinished:
            c = min(downs, key=lambda x: x["delta_pence"])
            out.append({"kind": "down", "category": c["category"],
                        "text": f"You spent {_pounds(c['delta_pence'])} less on {_label(c['category'])} than last month."})

    unsorted = next((c for c in cats if c["category"] == "Other"), None)
    if unsorted and unsorted["spend_pence"] >= 1000:
        out.append({"kind": "unsorted", "category": "Other",
                    "text": f"{_pounds(unsorted['spend_pence'])} of spending isn't sorted into a category yet. "
                            f"Sort it once and similar payments follow."})

    if tt["paid_back_pence"] > 0:
        out.append({"kind": "paid_back",
                    "text": f"People paid you back {_pounds(tt['paid_back_pence'])}. That's taken off your spending, "
                            f"not counted as earnings."})

    if tt["from_people_pence"] > 0:
        out.append({"kind": "from_people", "category": "From people",
                    "text": f"{_pounds(tt['from_people_pence'])} came in from people without a note saying what for. "
                            f"It isn't counted as earnings or spending."})

    salary = [t for t in mt if t.category == "Salary"]
    if salary:
        total = _pounds(sum(t.amount_pence for t in salary))
        when = (f"came in on the {_ordinal(salary[-1].date.day)}" if len(salary) == 1
                else f"came in over {len(salary)} payments")
        out.append({"kind": "salary", "text": f"Your pay of {total} {when}."})
    elif unfinished:
        days = [t.date.day for t in txns if t.category == "Salary"]
        if days:
            usual = sorted(days)[len(days) // 2]
            out.append({"kind": "salary", "text": f"Your salary usually arrives around the {_ordinal(usual)}. "
                                                  f"It isn't in these statements yet."})
    return out


def _label(category: str) -> str:
    return "unsorted spending" if category == "Other" else category.lower()
