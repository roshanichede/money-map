"""Find recurring payments (subscriptions, bills, rent) from regular intervals and stable amounts."""
import calendar
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from .models import Transaction

PERIODS = [  # name, typical days, tolerance in days
    ("weekly", 7, 1.5),
    ("fortnightly", 14, 2),
    ("monthly", 30.4, 4),
    ("quarterly", 91, 7),
    ("yearly", 365, 10),
]


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def detect_recurring(txns: list[Transaction], as_of: date | None = None) -> list[dict]:
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in txns:
        if t.amount_pence < 0 and t.category not in ("Transfers", "Cash"):
            groups[t.merchant_key].append(t)
    if as_of is None:
        as_of = max((t.date for t in txns), default=date.today())

    found = []
    for key, items in groups.items():
        items.sort(key=lambda t: t.date)
        # one charge per day per merchant counts once (avoids splitting a basket)
        by_day: dict[date, int] = {}
        for t in items:
            by_day[t.date] = by_day.get(t.date, 0) + t.amount_pence
        dates = sorted(by_day)
        if len(dates) < 3:
            continue
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        typical = median(gaps)
        period = next((p for p in PERIODS if abs(typical - p[1]) <= p[2]), None)
        if period is None:
            continue
        name, days, tol = period
        regular = sum(abs(g - days) <= tol * 1.5 for g in gaps) / len(gaps)
        amounts = [-by_day[d] for d in dates]
        typical_amount = int(median(amounts))
        stable = sum(abs(a - typical_amount) <= max(0.2 * typical_amount, 100) for a in amounts) / len(amounts)
        if regular < 0.75 or stable < 0.6:
            continue
        last = dates[-1]
        if name == "monthly":
            next_date = _add_months(last, 1)
        elif name == "quarterly":
            next_date = _add_months(last, 3)
        elif name == "yearly":
            next_date = _add_months(last, 12)
        else:
            next_date = last + timedelta(days=days)
        active = (as_of - last).days <= days * 1.6
        sample = items[-1]
        found.append({
            "merchant": sample.merchant,
            "merchant_key": key,
            "category": sample.category,
            "frequency": name,
            "typical_amount_pence": typical_amount,
            "amount_varies": stable < 1.0,
            "last_date": last.isoformat(),
            "next_expected": next_date.isoformat(),
            "occurrences": len(dates),
            "active": active,
            "monthly_cost_pence": int(typical_amount * 30.4 / days),
        })
    found.sort(key=lambda r: (not r["active"], -r["monthly_cost_pence"]))
    return found
