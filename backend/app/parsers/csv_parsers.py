"""CSV statement parsers: Lloyds Banking Group format first, then a header-sniffing generic parser."""
import csv
import io
import re
from collections import Counter

from .common import ParsedTxn, ParseError, ParseResult, guess_bank, parse_date, parse_money

# Lloyds, Halifax and Bank of Scotland share this export layout.
LLOYDS_HEADER = [
    "transaction date", "transaction type", "sort code", "account number",
    "transaction description", "debit amount", "credit amount", "balance",
]

# Column names, most specific first. Headers are normalised: lower case, no "(inr)"/"(£)", no dots.
DATE_NAMES = ("transaction date", "txn date", "tran date", "trans date", "date", "posted date", "posting date",
              "completed date", "value date", "value dt")
DESC_NAMES = ("transaction description", "description", "narration", "transaction remarks", "remarks",
              "particulars", "details", "transaction details", "narrative", "name", "merchant", "payee",
              "reference", "memo", "counter party")
AMOUNT_NAMES = ("amount", "value", "amount (gbp)", "amount(gbp)", "transaction amount", "local amount", "txn amount")
OUT_NAMES = ("debit amount", "debit", "paid out", "money out", "withdrawals", "withdrawal amt", "withdrawal amount",
             "withdrawal", "debits", "dr amount", "dr", "out")
IN_NAMES = ("credit amount", "credit", "paid in", "money in", "deposits", "deposit amt", "deposit amount",
            "deposit", "credits", "cr amount", "cr", "in")
BALANCE_NAMES = ("balance", "running balance", "balance (gbp)", "closing balance", "available balance", "bal")
TYPE_NAMES = ("transaction type", "type")
DRCR_NAMES = ("dr / cr", "dr/cr", "cr/dr", "debit/credit", "debit / credit", "dr cr", "cr dr")
ACCOUNT_NAMES = ("account number", "account")

def _read_rows(content: bytes) -> list[list[str]]:
    from .tables import read_csv

    return read_csv(content)


def _norm(header: list[str]) -> list[str]:
    out = []
    for h in header:
        h = h.strip().strip('"').lower().replace("\n", " ")
        h = re.sub(r"\((?:inr|₹|rs\.?|gbp|£)\s*\)|\b(?:inr|in rs)\b|[₹£]", "", h)
        h = re.sub(r"\.(?=\s|$)", "", h).replace(".", " ")
        out.append(" ".join(h.split()))
    return out


def is_lloyds(content: bytes) -> bool:
    try:
        header = _norm(_read_rows(content)[0])
    except ParseError:
        return False
    return header[: len(LLOYDS_HEADER)] == LLOYDS_HEADER


def _find(header: list[str], names: tuple[str, ...]) -> int | None:
    for name in names:
        if name in header:
            return header.index(name)
    return None


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def _balance_mismatches(txns: list[ParsedTxn]) -> int:
    bad = 0
    for prev, cur in zip(txns, txns[1:]):
        if prev.balance_pence is not None and cur.balance_pence is not None:
            if prev.balance_pence + cur.amount_pence != cur.balance_pence:
                bad += 1
    return bad


def to_chronological(txns: list[ParsedTxn]) -> list[ParsedTxn]:
    """Banks export newest-first or oldest-first. Pick the order where running balances add up;
    fall back to dates."""
    if len(txns) < 2:
        return txns
    forward, backward = txns, list(reversed(txns))
    if any(t.balance_pence is not None for t in txns):
        f_bad, b_bad = _balance_mismatches(forward), _balance_mismatches(backward)
        if f_bad != b_bad:
            return forward if f_bad < b_bad else backward
    return backward if txns[0].date > txns[-1].date else forward


def parse_lloyds_csv(content: bytes) -> ParseResult:
    rows = _read_rows(content)
    header = _norm(rows[0])
    if header[: len(LLOYDS_HEADER)] != LLOYDS_HEADER:
        raise ParseError("Not a Lloyds-format CSV.")
    txns: list[ParsedTxn] = []
    for line_no, row in enumerate(rows[1:], start=2):
        try:
            debit = parse_money(_cell(row, 5)) or 0
            credit = parse_money(_cell(row, 6)) or 0
            txns.append(ParsedTxn(
                date=parse_date(_cell(row, 0)),
                txn_type=_cell(row, 1).upper(),
                account=_cell(row, 3).lstrip("'"),
                description=" ".join(_cell(row, 4).split()),
                amount_pence=credit - abs(debit),
                balance_pence=parse_money(_cell(row, 7)),
            ))
        except ParseError as exc:
            raise ParseError(f"Line {line_no}: {exc}") from exc
    accounts = Counter(t.account for t in txns if t.account)
    return ParseResult("lloyds_csv", to_chronological(txns),
                       account_number=accounts.most_common(1)[0][0] if accounts else None, bank="Lloyds")


def _header_at(rows: list[list[str]]) -> int | None:
    """Banks (Indian ones especially) put account details above the table: find the real header row."""
    for i, row in enumerate(rows[:80]):
        h = _norm(row)
        has_amount = any(_find(h, names) is not None for names in (AMOUNT_NAMES, OUT_NAMES, IN_NAMES))
        if _find(h, DATE_NAMES) is not None and _find(h, DESC_NAMES) is not None and has_amount:
            return i
    return None


def parse_rows(rows: list[list[str]], source_format: str) -> ParseResult:
    at = _header_at(rows)
    if at is None:
        raise ParseError(
            "Couldn't find date, description and amount columns. "
            f"First row: {', '.join(c for c in rows[0] if c)[:200]}"
        )
    header = _norm(rows[at])
    i_date = _find(header, DATE_NAMES)
    i_desc = _find(header, DESC_NAMES)
    i_amount = _find(header, AMOUNT_NAMES)
    i_out = _find(header, OUT_NAMES)
    i_in = _find(header, IN_NAMES)
    i_bal = _find(header, BALANCE_NAMES)
    i_type = _find(header, TYPE_NAMES)
    i_drcr = _find(header, DRCR_NAMES)
    i_acct = _find(header, ACCOUNT_NAMES)
    preamble = " ".join(" ".join(r) for r in rows[:at]).lower()
    txns: list[ParsedTxn] = []
    skipped = 0
    for line_no, row in enumerate(rows[at + 1:], start=at + 2):
        date_cell = _cell(row, i_date)
        try:
            when = parse_date(date_cell)
        except ParseError:
            skipped += bool(date_cell)  # separator rows (****), totals and footers have no real date
            continue
        try:
            if i_amount is not None and (i_out is None or i_in is None):
                amount = parse_money(_cell(row, i_amount))
                if amount is not None and i_drcr is not None:
                    flag = _cell(row, i_drcr).upper()
                    amount = -abs(amount) if flag.startswith("D") else abs(amount) if flag.startswith("C") else amount
            else:
                amount = (parse_money(_cell(row, i_in)) or 0) - abs(parse_money(_cell(row, i_out)) or 0)
        except ParseError as exc:
            raise ParseError(f"Line {line_no}: {exc}") from exc
        if amount is None or (amount == 0 and i_amount is None):
            continue
        balance = None
        if i_bal is not None:
            try:
                balance = parse_money(_cell(row, i_bal))
            except ParseError:
                balance = None
        txns.append(ParsedTxn(
            date=when,
            description=" ".join(_cell(row, i_desc).split()) or "(no description)",
            amount_pence=amount,
            balance_pence=balance,
            txn_type=_cell(row, i_type).upper()[:20] if i_type is not None else "",
            account=_cell(row, i_acct),
        ))
    if not txns:
        raise ParseError("Found the table, but no transactions with a date and an amount in it.")
    accounts = Counter(t.account for t in txns if t.account and any(c.isdigit() for c in t.account))
    number = accounts.most_common(1)[0][0] if accounts else None
    if not number:
        m = re.search(r"account\s*(?:no|number|#)\.?\s*:?\s*([x*\d][x*\d\s-]{6,})", preamble)
        number = re.sub(r"\D", "", m.group(1)) if m and sum(ch.isdigit() for ch in m.group(1)) >= 6 else None
    raw_header = " ".join(rows[at]).lower()
    currency = None
    if "inr" in raw_header or "₹" in raw_header or "₹" in preamble or re.search(r"\binr\b|\brs\.", preamble):
        currency = "INR"
    elif "£" in raw_header or "gbp" in raw_header:
        currency = "GBP"
    return ParseResult(source_format, to_chronological(txns), account_number=number,
                       bank=guess_bank(preamble) if preamble else None, currency=currency,
                       warnings=[f"Skipped {skipped} rows without a date."] if skipped else None)


def parse_generic_csv(content: bytes) -> ParseResult:
    return parse_rows(_read_rows(content), "generic_csv")
