"""Tables. Money is stored as integer pence: negative = money out, positive = money in.

Every row belongs to a user. Account numbers are never stored in full: only the last four digits
(for display) and a salted hash (to recognise the same account in a later upload).
"""
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


ACCOUNT_TYPES = ("current", "savings", "credit_card", "other")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    bank: Mapped[str] = mapped_column(String(60), default="")
    account_type: Mapped[str] = mapped_column(String(20), default="current")
    last4: Mapped[str] = mapped_column(String(4), default="")
    number_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    source_format: Mapped[str] = mapped_column(String(40))  # lloyds_csv | generic_csv | pdf
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_added: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, default=0)
    reconciled: Mapped[str] = mapped_column(String(20), default="not_checked")  # ok | mismatch | not_checked
    reconciliation_note: Mapped[str] = mapped_column(Text, default="")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_txn_user_dedupe"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(255))
    merchant: Mapped[str] = mapped_column(String(120), index=True)  # display name, e.g. "Deliveroo"
    merchant_key: Mapped[str] = mapped_column(String(120), index=True)  # normalised key, e.g. "DELIVEROO"
    txn_type: Mapped[str] = mapped_column(String(20), default="")  # bank code, e.g. DEB, DD, FPI
    amount_pence: Mapped[int] = mapped_column(Integer)
    balance_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(40), index=True, default="Other")
    category_source: Mapped[str] = mapped_column(String(10), default="rule")  # rule | learned | manual | transfer
    transfer_pair_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # the matching leg in another account
    dedupe_key: Mapped[str] = mapped_column(String(64))


class MerchantRule(Base):
    """A category the user taught us: every transaction with this merchant_key gets it."""

    __tablename__ = "merchant_rules"
    __table_args__ = (UniqueConstraint("user_id", "merchant_key", name="uq_rule_user_merchant"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    merchant_key: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
