"""Import a parsed statement: pick the account, reconcile balances, drop duplicates, categorise, store,
then match transfers between the user's own accounts."""
import copy
import hashlib
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from .accounts import create_account, find_by_number, find_by_overlap, guess_type
from .categories import categorise
from .merchants import normalise
from .models import Account, MerchantRule, Transaction, Upload
from .money import fmt_gbp
from .parsers import ParseResult, parse_statement
from .transfers import link_transfers


class AccountChoiceError(ValueError):
    pass


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


def dedupe_keys(result: ParseResult, account_id: int) -> list[str]:
    """Same transaction in the same account => same key, whichever file (CSV or PDF) it came from.

    With a running balance, date + amount + balance-after identifies a row even when a CSV and a PDF
    word the description differently. Without one, the description is used. Identical rows inside one
    file get an occurrence number, so genuine repeats are kept but re-uploads are skipped.
    """
    seen: Counter = Counter()
    keys = []
    for t in result.transactions:
        if t.balance_pence is not None:
            base = f"{account_id}|bal|{t.date.isoformat()}|{t.amount_pence}|{t.balance_pence}"
        else:
            base = f"{account_id}|desc|{t.date.isoformat()}|{t.amount_pence}|{' '.join(t.description.upper().split())}"
        seen[base] += 1
        keys.append(hashlib.sha256(f"{base}|#{seen[base]}".encode()).hexdigest())
    return keys


def _fix_card_signs(result: ParseResult) -> bool:
    """Card exports usually list purchases as positive. On a card, purchases far outnumber repayments,
    so if most amounts are positive the signs are flipped to money-out-is-negative."""
    if any(t.balance_pence is not None for t in result.transactions):
        return False
    positive = sum(t.amount_pence > 0 for t in result.transactions)
    if positive > len(result.transactions) / 2:
        for t in result.transactions:
            t.amount_pence = -t.amount_pence
        return True
    return False


def choose_account(session: Session, user_id: int, filename: str, result: ParseResult,
                   account_id: int | None = None, new_account_type: str | None = None,
                   new_account_name: str | None = None) -> tuple[Account, str]:
    """Returns (account, how it was chosen). Order: the user's explicit choice, the account number in the
    file, overlap with transactions already imported, otherwise a new account."""
    if account_id is not None:
        acct = session.get(Account, account_id)
        if acct is None or acct.user_id != user_id:
            raise AccountChoiceError("That account doesn't exist.")
        return acct, "chosen"
    if result.account_number:
        acct = find_by_number(session, user_id, result.account_number)
        if acct:
            return acct, "matched by account number"
    else:
        # Try the file as it is and, for card-style files, with purchases flipped to negative.
        variants = [result]
        if not any(t.balance_pence is not None for t in result.transactions):
            flipped = copy.deepcopy(result)
            for t in flipped.transactions:
                t.amount_pence = -t.amount_pence
            variants.append(flipped)
        for variant in variants:
            acct = find_by_overlap(session, user_id, lambda aid, v=variant: dedupe_keys(v, aid))
            if acct:
                return acct, "matched to transactions already imported"
    acct = create_account(session, user_id, number=result.account_number, bank=result.bank,
                          account_type=new_account_type or guess_type(filename, result), name=new_account_name)
    return acct, "new account"


def import_file(session: Session, user_id: int, filename: str, content: bytes, *, account_id: int | None = None,
                new_account_type: str | None = None, new_account_name: str | None = None) -> Upload:
    result = parse_statement(filename, content)
    account, how = choose_account(session, user_id, filename, result, account_id, new_account_type, new_account_name)
    flipped = account.account_type == "credit_card" and _fix_card_signs(result)
    status, note = reconcile(result)
    if flipped:
        note += " Purchases on this card were shown as positive amounts, so they were turned into spending."
    upload = Upload(user_id=user_id, account_id=account.id, filename=filename[:255],
                    source_format=result.source_format, rows_read=len(result.transactions),
                    reconciled=status, reconciliation_note=note)
    upload.account_match = how  # not stored; returned to the caller
    session.add(upload)
    session.flush()

    keys = dedupe_keys(result, account.id)
    existing = set(session.scalars(select(Transaction.dedupe_key).where(
        Transaction.user_id == user_id, Transaction.dedupe_key.in_(keys))))
    rules = {r.merchant_key: r.category
             for r in session.scalars(select(MerchantRule).where(MerchantRule.user_id == user_id))}
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
            user_id=user_id, account_id=account.id, upload_id=upload.id, date=t.date,
            description=t.description[:255], merchant=merchant, merchant_key=merchant_key, txn_type=t.txn_type,
            amount_pence=t.amount_pence, balance_pence=t.balance_pence,
            category=category, category_source=source, dedupe_key=key,
        ))
        added += 1
    upload.rows_added = added
    upload.duplicates_skipped = len(result.transactions) - added
    session.flush()
    upload.transfers_matched = link_transfers(session, user_id)
    session.commit()
    return upload
