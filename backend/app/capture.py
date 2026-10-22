"""Live capture: payments sent from your phone the moment they happen, before any statement.

Two sources, both from the iPhone Shortcuts app posting to a private link:
  - Apple Pay: the Wallet "Transaction" automation sends merchant, amount and card for every tap.
  - Bank SMS: a Messages automation forwards texts like "Rs.450.00 debited from a/c XX1234 ... to VPA
    swiggy@icici". Indian banks text every debit and credit, UPI included.

A captured payment is stored as *pending*. When the statement for that account is uploaded later, the
statement row replaces it (same account, same amount, within a few days), carrying over any category
you set by hand, so nothing is counted twice.

Each link is a random token tied to one account; only its SHA-256 hash is stored, so the database alone
can't be used to post payments. The link is shown once, when it's created.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories import categorise
from .merchants import mask_numbers, normalise
from .models import Account, CaptureKey, Transaction, Upload
from .parsers.common import ParseError, parse_date, parse_money
from .parsers.india import clean as clean_indian

SOURCES = ("applepay", "sms")
MATCH_DAYS = 4  # card payments can take a few days to appear on a statement


def new_token() -> str:
    return secrets.token_urlsafe(24)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- reading what the phone sent ----------

_AMOUNT = re.compile(r"(?:rs\.?|inr|₹|£|gbp)\s*(\d[\d,]*(?:\.\d{1,2})?)|(\d[\d,]*(?:\.\d{1,2})?)\s*(?:rs\.?|inr|₹)(?![a-z])", re.I)
_OUT = re.compile(r"\b(debited|spent|sent|paid|withdrawn|withdrawal|purchase|deducted|transferred|debit)\b", re.I)
_IN = re.compile(r"\b(credited|received|deposited|refund(?:ed)?|reversed|credit)\b", re.I)
_SKIP = re.compile(r"\b(otp|one time password|password|requested|request|will be debited|due on|due date|"
                   r"statement|bill generated|e-?mandate|autopay set|declined|failed|not processed|offer)\b", re.I)
_PAYEE_PATTERNS = [
    re.compile(r"\bvpa\s+([\w.\-]+@[\w.\-]+)", re.I),
    re.compile(r"\b(?:to|towards|trf to|info:?)\s+([A-Za-z][A-Za-z0-9 &.'\-]{1,40}?)(?=\s+(?:on|ref|upi|via|from|avl|avbl|bal|a/c|\(|is|-)\b|[.,;]|$)", re.I),
    re.compile(r"\bat\s+([A-Za-z0-9][A-Za-z0-9 &.'\-*]{1,40}?)(?=\s+(?:on|ref|via|avl|avbl|bal|using|with|txn)\b|[.,;]|$)", re.I),
    re.compile(r"\bfrom\s+([A-Za-z][A-Za-z0-9 &.'\-]{1,40}?)(?=\s+(?:on|ref|upi|via|avl|avbl|bal|a/c|\(|is)\b|[.,;]|$)", re.I),
]
_DATE = re.compile(r"\b(\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})\b")


class NotAPayment(ValueError):
    pass


def from_sms(text: str, today: date) -> tuple[date, str, int]:
    """(date, description, signed amount) from a bank text, or NotAPayment for OTPs, offers and reminders."""
    msg = " ".join(text.split())
    if _SKIP.search(msg):
        raise NotAPayment("Not a completed payment (OTP, reminder or offer).")
    out, inc = _OUT.search(msg), _IN.search(msg)
    if not out and not inc:
        raise NotAPayment("No debit or credit in this message.")
    m = _AMOUNT.search(msg)
    if not m:
        raise NotAPayment("No amount in this message.")
    amount = parse_money(m.group(1) or m.group(2))
    if not amount:
        raise NotAPayment("No amount in this message.")
    # whichever word comes first decides the direction ("credited ... debited from your friend's a/c" is rare)
    outgoing = bool(out) and (not inc or out.start() < inc.start())
    payee = ""
    for rx in _PAYEE_PATTERNS:
        if rx.pattern.startswith(r"\bfrom") and outgoing:
            continue  # "from a/c XX1234" is your own account when money goes out
        pm = rx.search(msg)
        if pm:
            payee = pm.group(1).strip(" .-")
            if "@" in payee:  # a UPI handle: name it from the part before @
                payee = re.sub(r"[._\d-]+", " ", payee.split("@")[0]).strip()
            if payee and not re.match(r"^(a/?c|your|xx|ac|account)\b", payee, re.I):
                break
            payee = ""
    when = today
    dm = _DATE.search(msg)
    if dm:
        try:
            when = parse_date(dm.group(1).replace("/", "-") if re.match(r"\d{1,2}/[A-Za-z]", dm.group(1)) else dm.group(1))
        except ParseError:
            when = today
        if when > today or (today - when).days > 60:
            when = today
    if outgoing and re.search(r"\batm\b|withdrawn|cash withdrawal", msg, re.I):
        return when, "ATM CASH WITHDRAWAL", -abs(amount)
    upi = bool(re.search(r"\bupi\b|\bvpa\b", msg, re.I))
    desc = f"{'UPI ' if upi else ''}{payee.upper() or ('MONEY OUT' if outgoing else 'MONEY IN')}"
    return when, clean_indian(desc), (-abs(amount) if outgoing else abs(amount))


def from_apple_pay(merchant: str, amount: str, today: date) -> tuple[date, str, int]:
    value = parse_money(re.sub(r"[^\d.,\-£₹$€]", "", amount or ""))
    if not value:
        raise NotAPayment("No amount.")
    name = " ".join((merchant or "Apple Pay").split())[:120]
    return today, f"DEB {name.upper()}", -abs(value)  # a Wallet tap is money going out


# ---------- storing ----------

def _live_upload(session: Session, key: CaptureKey) -> Upload:
    up = session.scalar(select(Upload).where(Upload.user_id == key.user_id, Upload.account_id == key.account_id,
                                             Upload.source_format == "live"))
    if up is None:
        up = Upload(user_id=key.user_id, account_id=key.account_id, filename="Sent from your phone",
                    source_format="live", reconciled="not_checked",
                    reconciliation_note="Payments sent from your phone, waiting for the statement.")
        session.add(up)
        session.flush()
    return up


def record(session: Session, key: CaptureKey, when: date, description: str, amount: int) -> Transaction:
    from .learning import apply_rules

    description = mask_numbers(description)[:255]
    merchant_key, merchant = normalise(description)
    t = Transaction(user_id=key.user_id, account_id=key.account_id, upload_id=_live_upload(session, key).id,
                    date=when, description=description, merchant=merchant, merchant_key=merchant_key,
                    txn_type="", amount_pence=amount,
                    category=categorise(description, merchant_key, "", amount), category_source="rule",
                    dedupe_key=f"live:{uuid.uuid4().hex}", pending=True)
    session.add(t)
    session.flush()
    apply_rules(session, key.user_id)  # your taught rules apply straight away
    key.last_used = datetime.now(timezone.utc).replace(tzinfo=None)
    key.uses += 1
    session.commit()
    return t


def settle(session: Session, account_id: int, statement_rows: list[Transaction]) -> int:
    """The statement arrived: each statement row replaces the pending phone entry it matches."""
    pending = list(session.scalars(select(Transaction).where(Transaction.account_id == account_id,
                                                             Transaction.pending.is_(True))))
    if not pending:
        return 0
    settled = 0
    for row in sorted(statement_rows, key=lambda r: r.date):
        candidates = [p for p in pending if p.amount_pence == row.amount_pence
                      and abs((row.date - p.date).days) <= MATCH_DAYS]
        if not candidates:
            continue
        p = min(candidates, key=lambda p: (abs((row.date - p.date).days), p.id))
        if p.category_source == "manual":  # a category you chose on the phone entry carries over
            row.category, row.category_source = p.category, "manual"
        pending.remove(p)
        session.delete(p)
        settled += 1
    return settled


# ---------- a simple per-link rate limit ----------

class _Limit:
    def __init__(self, per_hour: int = 120):
        self.per_hour = per_hour
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        q = self.hits[key]
        now = time.monotonic()
        while q and q[0] < now - 3600:
            q.popleft()
        if len(q) >= self.per_hour:
            return False
        q.append(now)
        return True


limit = _Limit()


def find_key(session: Session, token: str) -> CaptureKey | None:
    if not token or len(token) > 100:
        return None
    key = session.scalar(select(CaptureKey).where(CaptureKey.token_hash == token_hash(token)))
    if key is None or key.revoked:
        return None
    acct = session.get(Account, key.account_id)
    return key if acct is not None else None
