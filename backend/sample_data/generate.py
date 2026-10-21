"""Generate synthetic Lloyds-format statements for demos and tests (no real data).

Creates three accounts for one person:
  lloyds_export_1.csv, lloyds_export_2.csv  - current account, two overlapping CSV exports (newest first)
  lloyds_statement_2026-09.pdf               - the same current account's September PDF statement
  lloyds_savings.csv                         - savings account fed by a monthly transfer from current
  lloyds_credit_card.csv                     - credit card (purchases positive, like most card exports),
                                               paid off monthly by direct debit from the current account
Run:  python sample_data/generate.py
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent
ACCOUNT, SAVINGS, SORT = "12345678", "87654321", "'30-99-50"
random.seed(42)
START, END = date(2026, 5, 1), date(2026, 10, 20)


def card_purchases(start: date, end: date):
    rng = random.Random(7)
    rows = []  # (date, description, amount_pence) with purchases positive
    shops = [("AMAZON.CO.UK*2K4LP0", 0.10, (899, 4599)), ("ASOS.COM LTD", 0.04, (1800, 6500)),
             ("NANDOS LEICESTER", 0.06, (1450, 3800)), ("TRAINLINE.COM", 0.04, (1200, 5600)),
             ("ODEON CINEMAS", 0.03, (1100, 2600)), ("ZARA UK LTD", 0.02, (2500, 7900))]
    d = start
    while d <= end:
        for desc, p, (lo, hi) in shops:
            if rng.random() < p:
                rows.append((d, desc, rng.randint(lo, hi)))
        d += timedelta(days=1)
    return rows


def card_repayments(purchases):
    """Each month's card bill is paid in full on the 10th of the next month."""
    totals: dict[tuple[int, int], int] = {}
    for d, _, amt in purchases:
        totals[(d.year, d.month)] = totals.get((d.year, d.month), 0) + amt
    pays = []
    for (y, m), total in sorted(totals.items()):
        pay_day = date(y + (m == 12), m % 12 + 1, 10)
        if pay_day <= END:
            pays.append((pay_day, total))
    return pays


def build_transactions(start: date, end: date, opening_pence: int, extra=()):
    rows = list(extra)  # (date, type, description, amount_pence)
    d = start
    while d <= end:
        dom = d.day
        if dom == 25:
            rows.append((d, "BGC", "ACME DIGITAL LTD SALARY", 248_500))
        if dom == 1:
            rows.append((d, "SO", "CITY LETTINGS RENT", -85_000))
        if dom == 3:
            rows.append((d, "DD", "OCTOPUS ENERGY", -random.choice([5_400, 5_900, 6_800])))
        if dom == 5:
            rows.append((d, "DD", "LEICESTER CITY COUNCIL CTAX", -13_200))
        if dom == 8:
            rows.append((d, "DD", "VODAFONE LIMITED", -1_800))
        if dom == 12:
            rows.append((d, "DEB", "NETFLIX.COM CD 4821", -1_099))
        if dom == 14:
            rows.append((d, "DEB", "SPOTIFY P2B7C9D1E CD 4821", -1_199))
        if dom == 20:
            rows.append((d, "DD", "PUREGYM LTD", -2_499))
        if dom == 18:
            rows.append((d, "DEB", "OPENAI *CHATGPT SUBSCR CD 4821", -1_600))
        if dom == 27:
            rows.append((d, "TFR", "TO A/C 87654321 SAVINGS", -30_000))
        if d.weekday() in (1, 5):
            shop = random.choice(["TESCO STORES 3021", "SAINSBURYS S/MKTS", "ALDI 84 LEICESTER", "LIDL GB LEICESTER"])
            rows.append((d, "DEB", f"{shop} CD 4821", -random.randint(1_800, 6_500)))
        if d.weekday() in (0, 2, 4) and random.random() < 0.7:
            rows.append((d, "DEB", "PRET A MANGER CD 4821", -random.choice([395, 450, 625])))
        if random.random() < (0.30 if d.month == 10 else 0.12):
            rows.append((d, "DEB", "DELIVEROO PLUS LONDON GB CD 4821", -random.randint(1_650, 3_400)))
        if random.random() < 0.18:
            rows.append((d, "DEB", "TFL TRAVEL CH TFL.GOV.UK/CP CD 4821", -random.choice([280, 560, 840])))
        if random.random() < 0.08:
            rows.append((d, "DEB", "AMZNMKTPLACE AMAZON.CO.UK CD 4821", -random.randint(899, 4_599)))
        if random.random() < 0.05:
            rows.append((d, "DEB", "UBER *TRIP HELP.UBER.COM CD 4821", -random.randint(900, 2_400)))
        if random.random() < 0.04:
            rows.append((d, "CPT", "LNK HIGH STREET LEICESTER", -random.choice([2_000, 4_000])))
        if random.random() < 0.03:
            rows.append((d, "FPI", "J SMITH DINNER SPLIT", random.choice([1_500, 2_250])))
        d += timedelta(days=1)
    if any(r[0] == date(2026, 10, 17) for r in rows) or start <= date(2026, 10, 17) <= end:
        rows.append((date(2026, 10, 17), "DEB", "RYANAIR LTD CD 4821", -18_900))
    # Money in that isn't salary: a freelance job, and friends paying back their share
    for when, typ, desc, amt in ((date(2026, 8, 21), "FPI", "BRIGHTPATH STUDIO LTD INV 014", 35_000),
                                 (date(2026, 9, 12), "DEB", "UBER *TRIP HELP.UBER.COM CD 4821", -2_380),
                                 (date(2026, 9, 13), "FPI", "PRIYA SHAH CAB", 1_190),
                                 (date(2026, 9, 26), "FPI", "RAHUL K FOOD", 1_850),
                                 (date(2026, 10, 11), "FPI", "ANNA LEE", 2_000)):
        if start <= when <= end:
            rows.append((when, typ, desc, amt))
    rows.sort(key=lambda r: r[0])
    balance = opening_pence
    out = []
    for d, typ, desc, amt in rows:
        balance += amt
        out.append((d, typ, desc, amt, balance))
    return out


def write_lloyds_csv(path: Path, txns, account: str = ACCOUNT):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Transaction Date", "Transaction Type", "Sort Code", "Account Number",
                    "Transaction Description", "Debit Amount", "Credit Amount", "Balance"])
        for d, typ, desc, amt, bal in reversed(txns):  # Lloyds exports newest first
            w.writerow([d.strftime("%d/%m/%Y"), typ, SORT, account, desc,
                        f"{-amt / 100:.2f}" if amt < 0 else "",
                        f"{amt / 100:.2f}" if amt > 0 else "", f"{bal / 100:.2f}"])


def write_pdf(path: Path, txns, opening_pence: int):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    cols = {"date": 40, "desc": 105, "type": 330, "in_r": 425, "out_r": 490, "bal_r": 560}

    def header(y):
        c.setFont("Helvetica-Bold", 8)
        c.drawString(cols["date"], y, "Date")
        c.drawString(cols["desc"], y, "Description")
        c.drawString(cols["type"], y, "Type")
        c.drawRightString(cols["in_r"], y, "Money In (£)")
        c.drawRightString(cols["out_r"], y, "Money Out (£)")
        c.drawRightString(cols["bal_r"], y, "Balance (£)")
        c.setFont("Helvetica", 8)

    def money(v):
        return f"{v / 100:,.2f}"

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, height - 50, "Classic Account statement — SAMPLE (synthetic data)")
    c.setFont("Helvetica", 8)
    c.drawString(40, height - 64, f"Account {ACCOUNT}   1 September 2026 to 30 September 2026")
    y = height - 95
    header(y)
    y -= 14
    c.drawString(cols["date"], y, txns[0][0].strftime("%d %b %y"))
    c.drawString(cols["desc"], y, "BALANCE BROUGHT FORWARD")
    c.drawRightString(cols["bal_r"], y, money(opening_pence))
    y -= 12
    for d, typ, desc, amt, bal in txns:
        if y < 60:
            c.showPage()
            y = height - 50
            header(y)
            y -= 14
        c.drawString(cols["date"], y, d.strftime("%d %b %y"))
        first, rest = (desc[:30], desc[30:]) if len(desc) > 30 else (desc, "")
        c.drawString(cols["desc"], y, first)
        c.drawString(cols["type"], y, typ)
        if amt > 0:
            c.drawRightString(cols["in_r"], y, money(amt))
        else:
            c.drawRightString(cols["out_r"], y, money(-amt))
        c.drawRightString(cols["bal_r"], y, money(bal))
        if rest:
            y -= 10
            c.drawString(cols["desc"], y, rest.strip())
        y -= 12
    c.drawString(cols["desc"], y, "BALANCE CARRIED FORWARD")
    c.drawRightString(cols["bal_r"], y, money(txns[-1][4]))
    c.save()


def write_card_csv(path: Path, purchases, repayments):
    rows = [(d, desc, amt) for d, desc, amt in purchases]
    rows += [(d + timedelta(days=1), "PAYMENT RECEIVED - THANK YOU", -amt) for d, amt in repayments]
    rows.sort(key=lambda r: r[0], reverse=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Date entered", "Reference", "Description", "Amount"])
        for i, (d, desc, amt) in enumerate(rows):
            w.writerow([d.strftime("%d/%m/%Y"), d.strftime("%d/%m/%Y"), f"REF{900000 + i}", desc, f"{amt / 100:.2f}"])


def build_savings(start: date, end: date, opening_pence: int):
    rows, balance, d = [], opening_pence, start
    while d <= end:
        if d.day == 1 and d != start:
            interest = round(balance * 0.035 / 12)
            balance += interest
            rows.append((d, "INT", "INTEREST (GROSS)", interest, balance))
        if d.day == 27:
            balance += 30_000
            rows.append((d, "TFR", f"FROM A/C {ACCOUNT}", 30_000, balance))
        d += timedelta(days=1)
    return rows


def main():
    opening = 182_340
    purchases = card_purchases(START, END)
    repayments = card_repayments(purchases)
    extra = [(d, "DD", "LLOYDS BANK PLC CREDIT CARD", -amt) for d, amt in repayments]
    txns = build_transactions(START, END, opening, extra)
    write_lloyds_csv(OUT / "lloyds_savings.csv", build_savings(START, END, 500_000), account=SAVINGS)
    write_card_csv(OUT / "lloyds_credit_card.csv", purchases, repayments)
    # Two overlapping exports, each capped like Lloyds' download (export 2 starts mid-August).
    write_lloyds_csv(OUT / "lloyds_export_1.csv", [t for t in txns if t[0] <= date(2026, 8, 31)])
    write_lloyds_csv(OUT / "lloyds_export_2.csv", [t for t in txns if t[0] >= date(2026, 8, 15)])
    sept = [t for t in txns if t[0].year == 2026 and t[0].month == 9]
    sept_opening = sept[0][4] - sept[0][3]
    write_pdf(OUT / "lloyds_statement_2026-09.pdf", sept, sept_opening)
    print(f"{len(txns)} transactions; export1={sum(t[0] <= date(2026,8,31) for t in txns)} "
          f"export2={sum(t[0] >= date(2026,8,15) for t in txns)} sept={len(sept)}")


if __name__ == "__main__":
    main()
