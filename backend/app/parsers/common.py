"""Shared parsing helpers."""
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


@dataclass
class ParsedTxn:
    date: date
    description: str
    amount_pence: int  # negative = money out
    balance_pence: int | None = None
    txn_type: str = ""
    account: str = ""


@dataclass
class ParseResult:
    source_format: str
    transactions: list[ParsedTxn]  # in chronological order (oldest first)
    opening_balance_pence: int | None = None
    warnings: list[str] | None = None


class ParseError(ValueError):
    pass


_DATE_FORMATS = (
    "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %b %y",
    "%d %B %Y", "%d-%b-%Y", "%d-%b-%y", "%d.%m.%Y", "%Y/%m/%d",
)


def parse_date(text: str) -> date:
    cleaned = " ".join(text.strip().replace(",", " ").split())
    # "01 Oct 2026T00:00" style or ISO timestamps
    cleaned = cleaned.split("T")[0] if re.match(r"^\d{4}-\d{2}-\d{2}T", cleaned) else cleaned
    if re.match(r"^\d{4}-\d{2}-\d{2} \d", cleaned):
        cleaned = cleaned.split(" ")[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    raise ParseError(f"Unrecognised date: {text!r}")


def parse_money(text: str | None) -> int | None:
    """'1,234.56' -> 123456 pence. Handles £, spaces, trailing CR/DR, (brackets) and minus."""
    if text is None:
        return None
    raw = str(text).strip().replace("£", "").replace(",", "").replace(" ", "")
    if raw in ("", "-", "—"):
        return None
    negative = False
    if raw.startswith("(") and raw.endswith(")"):
        negative, raw = True, raw[1:-1]
    upper = raw.upper()
    if upper.endswith("DR"):
        negative, raw = True, raw[:-2]
    elif upper.endswith("CR"):
        raw = raw[:-2]
    if raw.startswith("-"):
        negative, raw = not negative, raw[1:]
    elif raw.startswith("+"):
        raw = raw[1:]
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ParseError(f"Unrecognised amount: {text!r}") from exc
    pence = int((value * 100).quantize(Decimal("1")))
    return -pence if negative else pence
