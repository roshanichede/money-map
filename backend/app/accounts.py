"""Working out which of the user's accounts a statement belongs to."""
import hashlib
import os
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ACCOUNT_TYPES, Account, Transaction
from .parsers import ParseResult

TYPE_LABELS = {"current": "Current account", "savings": "Savings", "credit_card": "Credit card", "other": "Account"}
SHORT = {"current": "current account", "savings": "savings", "credit_card": "credit card", "other": "account"}


def number_hash(user_id: int, number: str) -> str:
    salt = os.environ.get("ACCOUNT_HASH_SALT", "moneymap-account-v1")
    digits = re.sub(r"\D", "", number)
    return hashlib.sha256(f"{salt}|{user_id}|{digits}".encode()).hexdigest()


def guess_type(filename: str, result: ParseResult) -> str:
    """Card exports rarely have a running balance and show repayments as "PAYMENT RECEIVED";
    a current account that *pays* a card mentions "CREDIT CARD" too, so descriptions alone aren't enough."""
    name = filename.upper()
    txns = result.transactions
    has_balance = any(t.balance_pence is not None for t in txns)
    descriptions = " ".join(t.description for t in txns[:300]).upper()
    if re.search(r"CREDIT.?CARD|\bCARD\b|AMEX|BARCLAYCARD", name):
        return "credit_card"
    if not has_balance and re.search(r"PAYMENT RECEIVED|PAYMENT - THANK|PAYMENT THANK YOU", descriptions):
        return "credit_card"
    if re.search(r"SAVINGS|SAVER|\bISA\b", name):
        return "savings"
    if txns and all(t.amount_pence > 0 or t.txn_type in ("TFR", "INT") for t in txns) and \
            sum(t.amount_pence > 0 for t in txns) / len(txns) >= 0.8:
        return "savings"
    return "current"


def default_name(account_type: str, bank: str | None, last4: str) -> str:
    """e.g. "Lloyds current account". The last four digits are shown alongside, not in the name."""
    return f"{bank} {SHORT[account_type]}" if bank else TYPE_LABELS[account_type]


def find_by_number(session: Session, user_id: int, number: str) -> Account | None:
    return session.scalar(select(Account).where(Account.user_id == user_id,
                                                Account.number_hash == number_hash(user_id, number)))


def find_by_overlap(session: Session, user_id: int, keys_for) -> Account | None:
    """A file with no account number: if most of its rows already exist in one account, it's that account."""
    best, best_share = None, 0.0
    for acct in session.scalars(select(Account).where(Account.user_id == user_id)):
        keys = keys_for(acct.id)
        if not keys:
            continue
        found = session.scalars(select(Transaction.dedupe_key).where(
            Transaction.user_id == user_id, Transaction.dedupe_key.in_(keys))).all()
        share = len(found) / len(keys)
        if share > best_share:
            best, best_share = acct, share
    return best if best_share >= 0.5 else None


def create_account(session: Session, user_id: int, *, number: str | None, bank: str | None,
                   account_type: str, name: str | None = None) -> Account:
    if account_type not in ACCOUNT_TYPES:
        account_type = "other"
    digits = re.sub(r"\D", "", number or "")
    last4 = digits[-4:] if digits else ""
    acct = Account(user_id=user_id, name=(name or default_name(account_type, bank, last4))[:120],
                   bank=bank or "", account_type=account_type, last4=last4,
                   number_hash=number_hash(user_id, digits) if digits else "")
    session.add(acct)
    session.flush()
    return acct
