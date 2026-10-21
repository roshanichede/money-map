"""PDF statement parser.

Works on text-based (not scanned) statements laid out as a table with a header row such as
"Date | Description | Type | Money In (£) | Money Out (£) | Balance (£)" (Lloyds' current layout).
Numbers are assigned to columns by horizontal position, so it copes with blank cells.
Where a statement has a single amount column, the sign is worked out from the running balance.
"""
import io
import re
from dataclasses import dataclass

import pdfplumber

from .common import ParsedTxn, ParseError, ParseResult, guess_bank, parse_date, parse_money

# 1,234.56 (UK) and 1,23,456.78 (Indian grouping), with an optional £/₹ and a trailing CR/DR.
MONEY_RE = re.compile(r"^-?[£₹]?\d{1,3}(,\d{2,3})*\.\d{2}(CR|DR|Cr|Dr)?$|^-?[£₹]?\d+\.\d{2}(CR|DR|Cr|Dr)?$")
DATE_PATTERNS = [
    re.compile(r"^(\d{1,2}) ([A-Za-z]{3,9}) (\d{2,4})$"),
    re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4})$"),
    re.compile(r"^(\d{4}-\d{2}-\d{2})$"),
    re.compile(r"^(\d{1,2}-\d{1,2}-\d{2,4})$"),
    re.compile(r"^(\d{1,2}-[A-Za-z]{3}-\d{2,4})$"),
]
OPENING_WORDS = ("balance brought forward", "opening balance", "balance b/f", "brought forward")
CLOSING_WORDS = ("balance carried forward", "closing balance", "balance c/f", "carried forward")
TYPE_CODE_RE = re.compile(r"^[A-Z]{2,4}$")
ACCOUNT_NO_RE = re.compile(r"account\s*(?:number|no\.?)?\s*:?\s*(\d{8}|\d{9,18})\b", re.I)


@dataclass
class Columns:
    desc_x0: float
    in_x1: float | None
    out_x1: float | None
    amount_x1: float | None
    balance_x1: float | None
    type_x0: float | None
    first_money_x0: float


def _lines(page) -> list[list[dict]]:
    words = page.extract_words(keep_blank_chars=False, x_tolerance=1.5, y_tolerance=2)
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    lines: list[list[dict]] = []
    for w in words:
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    return lines


def _phrase_x1(line: list[dict], *phrases: str) -> float | None:
    """Right edge of the first header phrase found (e.g. 'Money In')."""
    texts = [w["text"].lower().strip("()£₹:.") for w in line]
    for phrase in phrases:
        parts = phrase.split()
        for i in range(len(texts) - len(parts) + 1):
            if texts[i : i + len(parts)] == parts:
                end = line[i + len(parts) - 1]
                # include a trailing "(£)" token if present
                if i + len(parts) < len(line) and line[i + len(parts)]["text"].strip() in ("(£)", "£", "(₹)", "(INR)", "(inr)"):
                    end = line[i + len(parts)]
                return end["x1"]
    return None


def _header_columns(line: list[dict]) -> Columns | None:
    joined = " ".join(w["text"].lower() for w in line)
    if "balance" not in joined or "date" not in joined:
        return None
    in_x1 = _phrase_x1(line, "money in", "paid in", "deposit amt", "deposit amount", "deposits", "deposit",
                       "credit", "credits", "in")
    out_x1 = _phrase_x1(line, "money out", "paid out", "withdrawal amt", "withdrawal amount", "withdrawals",
                        "withdrawal", "debit", "debits", "out")
    amount_x1 = _phrase_x1(line, "amount")
    balance_x1 = _phrase_x1(line, "balance")
    if balance_x1 is None or (in_x1 is None and out_x1 is None and amount_x1 is None):
        return None
    desc = next((w for w in line if w["text"].lower().strip(".") in ("description", "details", "transaction",
                                                                       "narration", "particulars", "remarks")), None)
    type_w = next((w for w in line if w["text"].lower() == "type"), None)
    money_x1s = [x for x in (in_x1, out_x1, amount_x1) if x is not None]
    return Columns(
        desc_x0=desc["x0"] if desc else line[1]["x0"],
        in_x1=in_x1, out_x1=out_x1, amount_x1=amount_x1, balance_x1=balance_x1,
        type_x0=type_w["x0"] if type_w else None,
        first_money_x0=min(money_x1s) - 70,
    )


def _leading_date(line: list[dict]):
    """Return (date, n_words) if the line starts with a date."""
    for n in (3, 1):
        if len(line) < n:
            continue
        text = " ".join(w["text"] for w in line[:n])
        if any(p.match(text) for p in DATE_PATTERNS):
            try:
                return parse_date(text), n
            except ParseError:
                continue
    return None, 0


def _nearest(x1: float, cols: Columns) -> str:
    options = {k: v for k, v in (("in", cols.in_x1), ("out", cols.out_x1),
                                 ("amount", cols.amount_x1), ("balance", cols.balance_x1)) if v is not None}
    return min(options, key=lambda k: abs(options[k] - x1))


def parse_pdf(content: bytes) -> ParseResult:
    try:
        pdf = pdfplumber.open(io.BytesIO(content))
    except Exception as exc:  # pdfplumber raises several types for bad files
        raise ParseError("Couldn't open this PDF.") from exc

    txns: list[ParsedTxn] = []
    raw_amounts: list[int | None] = []  # unsigned amount when only a single amount column exists
    opening: int | None = None
    warnings: list[str] = []
    with pdf:
        if not any((p.extract_text() or "").strip() for p in pdf.pages):
            raise ParseError("This PDF has no readable text (it may be a scan).")
        first_page = pdf.pages[0].extract_text() or ""
        account_match = ACCOUNT_NO_RE.search(first_page)
        bank = guess_bank(first_page)
        current_date = None
        last_line_bottom = None
        for page in pdf.pages:
            cols: Columns | None = None
            for line in _lines(page):
                if cols is None:
                    cols = _header_columns(line)
                    continue
                joined = " ".join(w["text"] for w in line).lower()
                if _header_columns(line):  # repeated header
                    continue
                txn_date, n_date = _leading_date(line)
                body = line[n_date:]
                money = [w for w in body if MONEY_RE.match(w["text"]) and w["x0"] >= cols.first_money_x0]
                text_words = [w for w in body if w not in money]

                if any(k in joined for k in OPENING_WORDS):
                    bal = [w for w in money if _nearest(w["x1"], cols) == "balance"]
                    if bal and opening is None and not txns:
                        opening = parse_money(bal[-1]["text"])
                    current_date = txn_date or current_date
                    continue
                if any(k in joined for k in CLOSING_WORDS):
                    continue

                if not money:
                    # continuation of a wrapped description
                    if (txns and txn_date is None and text_words
                            and text_words[0]["x0"] >= cols.desc_x0 - 3
                            and last_line_bottom is not None
                            and line[0]["top"] - last_line_bottom < 14):
                        txns[-1].description += " " + " ".join(w["text"] for w in text_words)
                        last_line_bottom = line[0]["bottom"]
                    continue

                if txn_date:
                    current_date = txn_date
                if current_date is None:
                    continue

                txn_type = ""
                if cols.type_x0 is not None:
                    for w in list(text_words):
                        if abs(w["x0"] - cols.type_x0) < 25 and TYPE_CODE_RE.match(w["text"]):
                            txn_type = w["text"]
                            text_words.remove(w)
                            break

                amt_in = amt_out = amt_single = balance = None
                for w in money:
                    col = _nearest(w["x1"], cols)
                    value = parse_money(w["text"])
                    if col == "in":
                        amt_in = abs(value)
                    elif col == "out":
                        amt_out = abs(value)
                    elif col == "amount":
                        amt_single = value
                    else:
                        balance = value

                if amt_in is None and amt_out is None and amt_single is None:
                    continue
                if amt_single is not None:
                    amount = amt_single
                    raw_amounts.append(abs(amt_single) if amt_single > 0 else None)
                else:
                    amount = (amt_in or 0) - (amt_out or 0)
                    raw_amounts.append(None)
                txns.append(ParsedTxn(
                    date=current_date,
                    description=" ".join(w["text"] for w in text_words) or "(no description)",
                    amount_pence=amount,
                    balance_pence=balance,
                    txn_type=txn_type,
                ))
                last_line_bottom = line[0]["bottom"]

    if not txns:
        raise ParseError("No transactions found. Is this a bank statement with a Balance column?")

    # Single unsigned amount column: take the sign from the running balance.
    prev_bal = opening
    for txn, unsigned in zip(txns, raw_amounts):
        if unsigned is not None and prev_bal is not None and txn.balance_pence is not None:
            if prev_bal - unsigned == txn.balance_pence:
                txn.amount_pence = -unsigned
        if txn.balance_pence is not None:
            prev_bal = txn.balance_pence
        elif prev_bal is not None:
            prev_bal += txn.amount_pence

    lower = first_page.lower()
    currency = "INR" if ("₹" in first_page or re.search(r"\binr\b|\brs\.", lower)) else (
        "GBP" if "£" in first_page else None)
    return ParseResult("pdf", txns, opening_balance_pence=opening, warnings=warnings or None,
                       account_number=account_match.group(1) if account_match else None, bank=bank,
                       currency=currency)
