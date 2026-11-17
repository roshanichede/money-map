"""Accessible PDFs hide screen-reader labels inside each cell; the reader must ignore text nobody can see."""
import io

from reportlab.pdfgen import canvas

from app.parsers.pdf_statement import parse_pdf

COLS = [("Date", 57, "l"), ("Description", 110, "l"), ("Type", 260, "l"),
        ("Money In (£)", 380, "r"), ("Money Out (£)", 460, "r"), ("Balance (£)", 540, "r")]


def _cell(c, text, x, align, y, hidden):
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 9)
    (c.drawRightString if align == "r" else c.drawString)(x, y, text)
    start = x - c.stringWidth(text, "Helvetica", 9) if align == "r" else x
    c.setFillColorRGB(1, 1, 1)  # the label a screen reader announces: 0.1pt, white, inside the visible word
    c.setFont("Helvetica", 0.1)
    c.drawString(start + 1, y + 8.9, hidden)  # top-aligned with the visible text, as in the real PDFs


def _statement(rows):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica", 9)
    c.drawString(57, 780, "Account Number 12345678")
    y = 740
    for name, x, align in COLS:
        _cell(c, name, x, align, y, "Column")
    for row in rows:
        y -= 14
        for (name, x, align), value in zip(COLS, row):
            _cell(c, value or "", x, align, y, name if value else "blank")
    c.save()
    return buf.getvalue()


def test_hidden_labels_are_ignored():
    pdf = _statement([
        ("01 Oct 26", "TFL TRAVEL CH", "DEB", "", "5.25", "460.45"),
        ("07 Oct 26", "PREETI MISAL", "FPO", "", "32.70", "427.75"),
        ("19 Oct 26", "R SISODIA", "FPI", "15.00", "", "442.75"),
    ])
    r = parse_pdf(pdf)
    got = [(t.date.isoformat(), t.description, t.txn_type, t.amount_pence) for t in r.transactions]
    assert got == [("2026-10-01", "TFL TRAVEL CH", "DEB", -525),
                   ("2026-10-07", "PREETI MISAL", "FPO", -3270),
                   ("2026-10-19", "R SISODIA", "FPI", 1500)]
