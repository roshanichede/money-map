"""CSV statement parsers: Lloyds Banking Group format first, then a header-sniffing generic parser."""
import csv
import io
from collections import Counter

from .common import ParsedTxn, ParseError, ParseResult, parse_date, parse_money

# Lloyds, Halifax and Bank of Scotland share this export layout.
LLOYDS_HEADER = [
    "transaction date", "transaction type", "sort code", "account number",
    "transaction description", "debit amount", "credit amount", "balance",
]

DATE_NAMES = ("transaction date", "date", "posted date", "posting date", "value date", "completed date")
DESC_NAMES = ("transaction description", "description", "details", "narrative", "name", "merchant",
              "payee", "reference", "memo", "counter party")
AMOUNT_NAMES = ("amount", "value", "amount (gbp)", "amount(gbp)", "transaction amount", "local amount")
OUT_NAMES = ("debit amount", "debit", "paid out", "money out", "withdrawals", "out")
IN_NAMES = ("credit amount", "credit", "paid in", "money in", "deposits", "in")
BALANCE_NAMES = ("balance", "running balance", "balance (gbp)")
TYPE_NAMES = ("transaction type", "type")
ACCOUNT_NAMES = ("account number", "account")


def _read_rows(content: bytes) -> list[list[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    rows = [r for r in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in r)]
    if not rows:
        raise ParseError("The file is empty.")
    return rows


def _norm(header: list[str]) -> list[str]:
    return [h.strip().strip('"').lower() for h in header]


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


def parse_generic_csv(content: bytes) -> ParseResult:
    rows = _read_rows(content)
    header = _norm(rows[0])
    i_date = _find(header, DATE_NAMES)
    i_desc = _find(header, DESC_NAMES)
    i_amount = _find(header, AMOUNT_NAMES)
    i_out = _find(header, OUT_NAMES)
    i_in = _find(header, IN_NAMES)
    i_bal = _find(header, BALANCE_NAMES)
    i_type = _find(header, TYPE_NAMES)
    i_acct = _find(header, ACCOUNT_NAMES)
    if i_date is None or i_desc is None or (i_amount is None and i_out is None and i_in is None):
        raise ParseError(
            "Couldn't find date, description and amount columns. "
            f"Columns found: {', '.join(rows[0])}"
        )
    txns: list[ParsedTxn] = []
    for line_no, row in enumerate(rows[1:], start=2):
        try:
            if i_amount is not None:
                amount = parse_money(_cell(row, i_amount))
            else:
                amount = (parse_money(_cell(row, i_in)) or 0) - abs(parse_money(_cell(row, i_out)) or 0)
            if amount is None:
                continue
            txns.append(ParsedTxn(
                date=parse_date(_cell(row, i_date)),
                description=" ".join(_cell(row, i_desc).split()) or "(no description)",
                amount_pence=amount,
                balance_pence=parse_money(_cell(row, i_bal)) if i_bal is not None else None,
                txn_type=_cell(row, i_type).upper()[:20],
                account=_cell(row, i_acct),
            ))
        except ParseError as exc:
            raise ParseError(f"Line {line_no}: {exc}") from exc
    accounts = Counter(t.account for t in txns if t.account and any(c.isdigit() for c in t.account))
    return ParseResult("generic_csv", to_chronological(txns),
                       account_number=accounts.most_common(1)[0][0] if accounts else None)
