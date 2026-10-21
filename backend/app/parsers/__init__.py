from .common import ParsedTxn, ParseError, ParseResult
from .csv_parsers import is_lloyds, parse_generic_csv, parse_lloyds_csv
from .pdf_statement import parse_pdf


def parse_statement(filename: str, content: bytes) -> ParseResult:
    name = filename.lower()
    if name.endswith(".pdf") or content[:5] == b"%PDF-":
        return parse_pdf(content)
    if name.endswith((".csv", ".txt")) or b"," in content[:2000]:
        if is_lloyds(content):
            return parse_lloyds_csv(content)
        return parse_generic_csv(content)
    raise ParseError("Unsupported file type. Upload a CSV export or a PDF statement.")


__all__ = ["ParsedTxn", "ParseError", "ParseResult", "parse_statement"]
