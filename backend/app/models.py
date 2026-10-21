"""Tables. Money is stored as integer pence: negative = money out, positive = money in."""
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
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
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_txn_dedupe"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"))
    account: Mapped[str] = mapped_column(String(64), default="")
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(255))
    merchant: Mapped[str] = mapped_column(String(120), index=True)  # display name, e.g. "Deliveroo"
    merchant_key: Mapped[str] = mapped_column(String(120), index=True)  # normalised key, e.g. "DELIVEROO"
    txn_type: Mapped[str] = mapped_column(String(20), default="")  # bank code, e.g. DEB, DD, FPI
    amount_pence: Mapped[int] = mapped_column(Integer)
    balance_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(40), index=True, default="Other")
    category_source: Mapped[str] = mapped_column(String(10), default="rule")  # rule | learned | manual
    dedupe_key: Mapped[str] = mapped_column(String(64))


class MerchantRule(Base):
    """A category the user taught us: every transaction with this merchant_key gets it."""

    __tablename__ = "merchant_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_key: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
