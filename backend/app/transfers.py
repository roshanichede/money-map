"""Match money moving between the user's own accounts, so it isn't counted as spending or income.

A transfer is two legs: money out of account A and the same amount into account B within a few days.
Typical cases: current account -> savings, and current account -> credit card repayment.
"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Transaction

WINDOW_DAYS = 4
TRANSFER_TYPES = {"TFR", "FPO", "FPI", "BGC", "SO", "DD", "BP", "PAY", "CR"}
TRANSFER_WORDS = re.compile(r"TRANSFER|\bA/C\b|SAVINGS|PAYMENT|CREDIT CARD|\bCARD\b|\bTO\b|\bFROM\b|\bPOT\b")
LIKELY_CATEGORIES = {"Transfers", "Card repayments", "Other income", "From people", "Other", "Bills & utilities"}


def _looks_like_transfer(t: Transaction) -> bool:
    return (t.txn_type in TRANSFER_TYPES or bool(TRANSFER_WORDS.search(t.description.upper()))
            or t.category in ("Transfers", "Card repayments"))


def link_transfers(session: Session, user_id: int) -> int:
    """Pair up unmatched legs across accounts. Returns the number of pairs made. Manual categories are respected."""
    txns = list(session.scalars(select(Transaction).where(
        Transaction.user_id == user_id, Transaction.transfer_pair_id.is_(None),
        Transaction.category_source != "manual").order_by(Transaction.date, Transaction.id)))
    if len({t.account_id for t in txns}) < 2:
        return 0
    incoming: dict[int, list[Transaction]] = {}
    for t in txns:
        if t.amount_pence > 0 and t.category in LIKELY_CATEGORIES:
            incoming.setdefault(t.amount_pence, []).append(t)
    pairs = 0
    for out in txns:
        if out.amount_pence >= 0 or out.transfer_pair_id is not None or out.category not in LIKELY_CATEGORIES:
            continue
        candidates = [i for i in incoming.get(-out.amount_pence, [])
                      if i.transfer_pair_id is None and i.account_id != out.account_id
                      and abs((i.date - out.date).days) <= WINDOW_DAYS
                      and (_looks_like_transfer(out) or _looks_like_transfer(i))]
        if not candidates:
            continue
        match = min(candidates, key=lambda i: (abs((i.date - out.date).days), i.id))
        for leg, other in ((out, match), (match, out)):
            leg.transfer_pair_id = other.id
            leg.category, leg.category_source = "Transfers", "transfer"
        pairs += 1
    return pairs


def unlink_account(session: Session, account_id: int) -> None:
    """Before deleting an account, release the other leg of its transfers back to normal categorising."""
    from .categories import categorise

    legs = session.scalars(select(Transaction).where(Transaction.account_id == account_id,
                                                     Transaction.transfer_pair_id.is_not(None)))
    for leg in legs:
        other = session.get(Transaction, leg.transfer_pair_id)
        if other is not None and other.account_id != account_id:
            other.transfer_pair_id = None
            other.category = categorise(other.description, other.merchant_key, other.txn_type, other.amount_pence)
            other.category_source = "rule"

