"""Spotting salary among money coming in, and re-sorting existing data when the rules improve."""
from collections import defaultdict
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories import OTHER_INCOME_RE, PAY_CODES, categorise, is_company, split_code
from .merchants import normalise
from .models import AppMeta, MerchantRule, Transaction, User

RULES_VERSION = 4  # bump when categorising rules change in a way existing data should pick up
MIN_PAY = {"GBP": 30_000, "INR": 1_000_000, "EUR": 30_000, "USD": 30_000}  # £300 / ₹10,000 in minor units


def detect_salary(session: Session, user_id: int) -> int:
    """Which income is your pay.

    - Paid by payroll (BGC/BACS) in two or more different months: salary, whatever the amounts
      (hourly and part-time pay varies a lot from month to month).
    - Otherwise a company paying you a similar amount (at least £300) in two or more months.
    Money from *people* (e.g. a flatmate's rent share) is never treated as salary."""
    rows = list(session.scalars(select(Transaction).where(
        Transaction.user_id == user_id, Transaction.amount_pence > 0,
        Transaction.category == "Other income", Transaction.category_source == "rule")))
    from .models import Account

    cur = {a.id: a.currency for a in session.scalars(select(Account).where(Account.user_id == user_id))}
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in rows:
        if OTHER_INCOME_RE.search(t.description.upper()):
            continue  # interest, HMRC, invoices...: income, but not pay
        payroll = split_code(t.description, t.txn_type)[0] in PAY_CODES
        if payroll or is_company(t.description):
            groups[("pay:" if payroll else "co:") + t.merchant_key].append(t)
    changed = 0
    for group, items in groups.items():
        months = {(t.date.year, t.date.month) for t in items}
        if len(months) < 2:
            continue
        if group.startswith("pay:"):
            chosen = items
        else:
            typical = median(t.amount_pence for t in items)
            if typical < MIN_PAY.get(cur.get(items[0].account_id, "GBP"), 30_000):
                continue
            chosen = [t for t in items if abs(t.amount_pence - typical) <= 0.35 * typical]
            if len({(t.date.year, t.date.month) for t in chosen}) < 2:
                continue
        for t in chosen:
            t.category = "Salary"
            changed += 1
    return changed


def upgrade_existing_data(session: Session) -> None:
    """Re-sort transactions imported under older rules. User-made choices are kept (only renamed)."""
    from .transfers import link_transfers

    meta = session.get(AppMeta, "rules_version")
    version = int(meta.value) if meta else 1
    if version >= RULES_VERSION:
        return
    renamed: dict[tuple[int, str], str] = {}  # (user, old merchant key) -> new key
    for t in session.scalars(select(Transaction)):
        key, name = normalise(t.description)
        if key != t.merchant_key:
            renamed[(t.user_id, t.merchant_key)] = key
        t.merchant_key, t.merchant = key, name
        if t.category_source == "rule":
            t.category = categorise(t.description, key, t.txn_type, t.amount_pence)
        elif t.category == "Income":  # the old single "Income" bucket
            t.category = "Other income"
    seen: set[tuple[int, str]] = set()
    rules = list(session.scalars(select(MerchantRule).order_by(MerchantRule.created_at.desc(), MerchantRule.id.desc())))
    keep = []
    for r in rules:  # newest first, so the latest choice wins if two old names now mean the same merchant
        new_key = renamed.get((r.user_id, r.merchant_key), r.merchant_key)
        if (r.user_id, new_key) in seen:
            session.delete(r)
        else:
            keep.append((r, new_key))
        seen.add((r.user_id, new_key))
    session.flush()  # deletes first, so renaming can't collide with the unique (user, merchant) rule
    for r, new_key in keep:
        r.merchant_key = new_key
        if r.category == "Income":
            r.category = "Other income"
    session.flush()
    from .learning import apply_rules

    for user in session.scalars(select(User)):
        apply_rules(session, user.id)
        detect_salary(session, user.id)
        link_transfers(session, user.id)
    if meta:
        meta.value = str(RULES_VERSION)
    else:
        session.add(AppMeta(key="rules_version", value=str(RULES_VERSION)))
    session.commit()
