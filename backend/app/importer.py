"""Import a parsed statement: reconcile balances, drop duplicates, categorise, store."""
import hashlib
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories import categorise
from .merchants import normalise
from .models import MerchantRule, Transaction, Upload
from .parsers import ParseResult, parse_statement
from .money import fmt_gbp


def reconcile(result: ParseResult) -> tuple[str, str]:
    """Check that every running balance equals previous balance + amount."""
    txns = result.transactions
    with_bal = [t for t in txns if t.balance_pence is not None]
    if not with_bal:
        return "not_checked", "This file has no balance column, so totals can't be checked."
    prev = result.opening_balance_pence
    if prev is None:
        first = txns[0]
        prev = first.balance_pence - first.amount_pence if first.balance_pence is not None else None
    opening = prev
    mismatches = []
    for t in txns:
        if prev is not None and t.balance_pence is not None and prev + t.amount_pence != t.balance_pence:
            mismatches.append(t)
        if t.balance_pence is not None:
            prev = t.balance_pence
        elif prev is not None:
            prev += t.amount_pence
    if mismatches:
        m = mismatches[0]
        return "mismatch", (
            f"{len(mismatches)} row(s) don't add up to the running balance; first on {m.date:%d %b %Y} "
            f"({m.description[:40]}). Some transactions may be missing from this file."
        )
    closing = with_bal[-1].balance_pence
    return "ok", (
        f"Opening balance {fmt_gbp(opening)} plus {len(txns)} transactions = closing balance "
        f"{fmt_gbp(closing)}, matching the statement to the penny."
    )


def _dedupe_keys(result: ParseResult) -> list[str]:
    """Same transaction => same key, whichever file (CSV or PDF) it came from.

    With a running balance, date + amount + balance-after identifies a row even when the CSV and PDF
    word the description differently. Without one, fall back to account + description. Identical rows
    inside one file get an occurrence number, so genuine repeats are kept but re-uploads are skipped.
    """
    seen: Counter = Counter()
    keys = []
    for t in result.transactions:
        if t.balance_pence is not None:
            base = f"bal|{t.date.isoformat()}|{t.amount_pence}|{t.balance_pence}"
        else:
            base = f"desc|{t.account}|{t.date.isoformat()}|{t.amount_pence}|{' '.join(t.description.upper().split())}"
        seen[base] += 1
        keys.append(hashlib.sha256(f"{base}|#{seen[base]}".encode()).hexdigest())
    return keys


def import_file(session: Session, filename: str, content: bytes) -> Upload:
    result = parse_statement(filename, content)
    status, note = reconcile(result)
    upload = Upload(filename=filename[:255], source_format=result.source_format,
                    rows_read=len(result.transactions), reconciled=status, reconciliation_note=note)
    session.add(upload)
    session.flush()

    keys = _dedupe_keys(result)
    existing = set(session.scalars(select(Transaction.dedupe_key).where(Transaction.dedupe_key.in_(keys))))
    rules = {r.merchant_key: r.category for r in session.scalars(select(MerchantRule))}
    added = 0
    for t, key in zip(result.transactions, keys):
        if key in existing:
            continue
        existing.add(key)
        merchant_key, merchant = normalise(t.description)
        if merchant_key in rules:
            category, source = rules[merchant_key], "learned"
        else:
            category, source = categorise(t.description, merchant_key, t.txn_type, t.amount_pence), "rule"
        session.add(Transaction(
            upload_id=upload.id, account=t.account, date=t.date, description=t.description[:255],
            merchant=merchant, merchant_key=merchant_key, txn_type=t.txn_type,
            amount_pence=t.amount_pence, balance_pence=t.balance_pence,
            category=category, category_source=source, dedupe_key=key,
        ))
        added += 1
    upload.rows_added = added
    upload.duplicates_skipped = len(result.transactions) - added
    session.commit()
    return upload
