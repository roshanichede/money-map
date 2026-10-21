"""Indian bank statements: make UPI / NEFT / IMPS / ATM / POS lines readable.

Each bank writes them differently, all as one string of codes:
  SBI     TO TRANSFER-UPI/DR/412345678901/PREETI M/SBIN/preetim@oksbi/rent--
  HDFC    UPI-SWIGGY-SWIGGY8.PAYU@HDFCBANK-HDFC0MERUPI-412345678901-PAYMENT FROM PHONE
  ICICI   UPI/412345678901/Dinner share/rahul.k@okicici/ICICI Bank
  Axis    UPI/P2A/412345678901/PREETI MISAL/SBI/rent
  Kotak   UPI/PREETI MISAL/412345678901/rent
  NEFT    NEFT CR-HDFC0000123-ACME TECHNOLOGIES PVT LTD-SALARY OCT-N123456789
  IMPS    IMPS-412345678901-ANIL KUMAR-SBIN-XXXXXXX1234-books
  ATM     ATW-512345XXXXXX1234-S1ANMU12-MUMBAI
  POS     POS 512345XXXXXX1234 DMART AVENUE

They become "CODE PAYEE NOTE", e.g. "UPI PREETI M RENT", "NEFT ACME TECHNOLOGIES PVT LTD SALARY OCT",
so the rest of MoneyMap (merchant names, categories, learned rules) works the same as for UK statements.
"""
import re

CODES = ("UPI", "NEFT", "IMPS", "RTGS")
_START = re.compile(r"^(?:(?:TO|BY)\s+TRANSFER[-\s]+|(?:DR|CR)[-\s]+)?(UPI|NEFT|IMPS|RTGS)\b(?:\s*(?:CR|DR|IN|OUT))?", re.I)
_IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_REF = re.compile(r"^(?=.*\d)[A-Z0-9]{6,}$")          # transaction references: long, contain a digit
_DIGITS = re.compile(r"^[\d\s•X*]+$")
_MASKED = re.compile(r"^[X*•\d]{4,}$")
BANK_WORDS = {
    "SBIN", "SBI", "HDFC", "HDFC BANK", "HDFCBANK", "ICIC", "ICICI", "ICICI BANK", "UTIB", "AXIS", "AXIS BANK", "KKBK",
    "KOTAK", "KOTAK MAHINDRA BANK", "YESB", "YES BANK", "IDFB", "IDFC FIRST", "BARB", "BANK OF BARODA", "PUNB", "PNB",
    "CNRB", "CANARA BANK", "UBIN", "UNION BANK", "INDB", "INDUSIND", "PYTM", "PAYTM", "PAYTM PAYMENTS BANK",
    "AIRP", "AIRTEL PAYMENTS BANK", "FDRL", "FEDERAL BANK", "IBKL", "IDBI", "CITI", "SCBL", "HSBC", "AUBL",
}
FILLER = {"DR", "CR", "P2A", "P2M", "P2P", "UPI", "NA", "N A", "NULL", "PAYMENT", "PAY", "PAYMENT FROM PHONE",
          "PAY TO", "SENT USING PAYTM UPI", "UPI INTENT", "COLLECT", "PAYMENT FOR", "PAYMENT TO", "PAID VIA",
          "TRANSFER", "IN", "OUT", "MOBILE", "MOB", "INB", "NETBANKING", "FT"}
_HANDLE_JUNK = re.compile(r"\d+|\b(PAYU|RAZORPAY|PAYTM|RZP|ICICI|HDFC|YBL|OK\w+|AXL|IBL|APL|UPI)\b", re.I)


def _from_handle(vpa: str) -> str:
    """'swiggy8.payu@hdfcbank' -> 'SWIGGY'; 'preetim@oksbi' -> 'PREETIM'."""
    user = vpa.split("@")[0]
    user = re.sub(r"[._-]+", " ", user)
    user = _HANDLE_JUNK.sub(" ", user.upper())
    return " ".join(user.split())


def clean(description: str) -> str:
    """Rewrite an Indian payment line as 'CODE PAYEE NOTE'. Other descriptions are returned unchanged."""
    text = " ".join(description.split())
    upper = text.upper()

    if re.match(r"^(ATW|NWD|ATM|EAW)\b|^ATM\s*(WDL|CASH)|^CASH\s*WDL", upper):
        words = [w for w in re.split(r"[\s/-]+", upper)
                 if w and not re.search(r"\d", w) and w not in {"ATW", "NWD", "ATM", "EAW", "WDL", "CASH"}]
        return " ".join(["ATM CASH WITHDRAWAL", *words[-1:]]).strip()
    pos = re.match(r"^(POS|PCD|ECOM|VPS|IPS)[\s/-]+(.*)$", upper)
    if pos:
        rest = [w for w in re.split(r"[\s/-]+", pos.group(2)) if w and not _MASKED.match(w) and not _REF.match(w)]
        return ("POS " + " ".join(rest)).strip()

    nach = re.match(r"^(?:NACH|ACH)[\s/-]*(?:DR|D|CR|C)?[\s/-]*(?:TP\s+)?(?:ACH\s+)?(.*)$", upper)
    if nach and upper.startswith(("NACH", "ACH")):
        rest = [w for w in re.split(r"[\s/-]+", nach.group(1)) if w and not _REF.match(w) and not _DIGITS.match(w)]
        return ("NACH " + " ".join(rest)).strip()

    m = _START.match(upper)
    if not m:
        return text
    code = m.group(1).upper()
    rest = text[m.end():]
    parts = [p.strip() for p in re.split(r"[/-]+", rest) if p.strip()]
    handle_name = ""
    kept: list[str] = []
    for p in parts:
        pu = p.upper()
        if "@" in p:
            handle_name = handle_name or _from_handle(p)
            continue
        squashed = pu.replace(" ", "")
        if (_IFSC.match(squashed) or _REF.match(squashed) or _DIGITS.match(p) or _MASKED.match(squashed)
                or pu in BANK_WORDS or pu in FILLER or squashed.startswith("••")):
            continue
        kept.append(pu)
    if not kept and handle_name:
        kept = [handle_name]
    elif (kept and handle_name and code == "UPI" and len(kept) == 1
          and kept[0] not in handle_name and handle_name not in kept[0]):
        # ICICI puts the note where others put the name; the handle names the payee.
        kept = [handle_name, kept[0]]
    return " ".join([code, *kept]).strip() or code


def looks_indian(descriptions: list[str]) -> bool:
    """Most lines are UPI / NEFT / IMPS: an Indian account even when the file never says ₹."""
    if not descriptions:
        return False
    hits = sum(1 for d in descriptions
               if _START.match(d.upper()) or re.match(r"^(ATW|NWD)-|^ATM\s*WDL|^NACH\b", d.upper()))
    # UPI / NEFT / IMPS don't exist outside India, so a few such lines are enough
    return hits >= max(1, 0.2 * len(descriptions))
