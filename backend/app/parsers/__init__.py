from .common import INDIAN_BANKS, ParsedTxn, ParseError, ParseResult
from .csv_parsers import is_lloyds, parse_generic_csv, parse_lloyds_csv, parse_rows
from .india import clean as clean_indian
from .india import looks_indian
from .pdf_statement import parse_pdf
from .tables import READERS, kind_of


def parse_statement(filename: str, content: bytes) -> ParseResult:
    kind = kind_of(filename, content)
    if kind == "pdf":
        result = parse_pdf(content)
    elif kind == "csv" and is_lloyds(content):
        result = parse_lloyds_csv(content)
    else:
        try:
            rows = READERS[kind](content)
        except ParseError:
            raise
        except Exception as exc:  # a corrupt or password-protected spreadsheet
            raise ParseError("That file couldn't be read. If it's password-protected, save an unprotected copy "
                             "or export CSV.") from exc
        result = parse_rows(rows, {"csv": "generic_csv", "xlsx": "excel", "xls": "excel", "html": "excel"}[kind])
    # Indian payment lines (UPI / NEFT / IMPS...) become "CODE PAYEE NOTE"; currency from the file or the lines.
    descriptions = [t.description for t in result.transactions]
    if result.currency is None:
        if (result.bank in INDIAN_BANKS) or looks_indian(descriptions):
            result.currency = "INR"
    for t in result.transactions:
        t.description = clean_indian(t.description)
    return result


__all__ = ["ParsedTxn", "ParseError", "ParseResult", "parse_statement"]
