"""Indian bank statements: Excel with a preamble, Indian column names, ₹ amounts, UPI/NEFT lines, currencies."""
import io

import openpyxl

from app.parsers import parse_statement
from app.parsers.india import clean

# HDFC-style: account details above the table, a row of asterisks under the header, dd/mm/yy dates
HDFC_TXT = """HDFC BANK Ltd.,,,,,,
Statement of account,,,,,,
Account No :,50100123456789,,,,,
Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
********,********,********,********,********,********,********
01/10/26,NEFT CR-HDFC0000123-ACME TECHNOLOGIES PVT LTD-SALARY OCT-N123456789,N123456789,01/10/26,,"85,000.00","1,10,000.00"
03/10/26,UPI-SWIGGY-SWIGGY8.PAYU@HDFCBANK-HDFC0MERUPI-412345678901-PAYMENT FROM PHONE,412345678901,03/10/26,456.00,,"1,09,544.00"
05/10/26,TO TRANSFER-UPI/DR/412345678901/PREETI M/SBIN/preetim@oksbi/rent--,412345678902,05/10/26,"18,000.00",,"91,544.00"
07/10/26,UPI/412345678901/Dinner share/rahul.k@okicici/ICICI Bank,412345678903,07/10/26,,600.00,"92,144.00"
09/10/26,ATW-512345XXXXXX1234-S1ANMU12-MUMBAI,000000000123,09/10/26,"2,000.00",,"90,144.00"
12/10/26,UPI/P2M/412345678901/BLINKIT/UPI/AXIS BANK,412345678904,12/10/26,345.00,,"89,799.00"
,,,,,,
STATEMENT SUMMARY :-,,,,,,
Opening Balance,Dr Count,Cr Count,Debits,Credits,Closing Bal,
"25,000.00",4,2,"20,801.00","85,600.00","89,799.00",
"""


def _xlsx(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_hdfc_style_statement():
    r = parse_statement("Acct_Statement_XX6789.txt", HDFC_TXT.encode())
    assert r.currency == "INR" and r.bank == "HDFC Bank"
    assert r.account_number == "50100123456789"
    assert [t.amount_pence for t in r.transactions] == [8500000, -45600, -1800000, 60000, -200000, -34500]
    assert r.transactions[0].balance_pence == 11000000  # Indian grouping 1,10,000.00
    assert [t.description for t in r.transactions][:3] == [
        "NEFT ACME TECHNOLOGIES PVT LTD SALARY OCT", "UPI SWIGGY", "UPI PREETI M RENT"]


def test_icici_style_excel_with_preamble():
    data = _xlsx([
        ["ICICI Bank Limited"], ["Account Number", "XXXXXXXX4321"], [],
        ["S No.", "Value Date", "Transaction Date", "Cheque Number", "Transaction Remarks",
         "Withdrawal Amount (INR )", "Deposit Amount (INR )", "Balance (INR )"],
        [1, "02/10/2026", "02/10/2026", "", "UPI/412345678901/Cab/ankit.s@okaxis/HDFC Bank", "", 250.0, 10250.0],
        [2, "04/10/2026", "04/10/2026", "", "UPI-ZEPTO-ZEPTO.PAYU@ICICI-ICIC0000001-412345678901-UPI", 512.5, "", 9737.5],
        [3, "06/10/2026", "06/10/2026", "", "NACH DR TP ACH LIC OF INDIA 12345", 2500.0, "", 7237.5],
    ])
    r = parse_statement("OpTransactionHistory.xlsx", data)
    assert r.source_format == "excel" and r.currency == "INR"
    assert [t.amount_pence for t in r.transactions] == [25000, -51250, -250000]
    assert r.transactions[0].description == "UPI ANKIT S CAB"


def test_sbi_style_csv_and_kotak_drcr_column():
    sbi = ("Txn Date,Value Date,Description,Ref No./Cheque No.,Debit,Credit,Balance\n"
           "1 Oct 2026,1 Oct 2026,BY TRANSFER-UPI/CR/412345678901/RAHUL K/HDFC/rahulk@okhdfcbank/cab--,,,120.00,5120.00\n"
           "2 Oct 2026,2 Oct 2026,ATM WDL-ATM CASH 1234 MUMBAI,,2000.00,,3120.00\n")
    r = parse_statement("sbi.csv", sbi.encode())
    assert r.currency == "INR" and [t.description for t in r.transactions] == ["UPI RAHUL K CAB", "ATM CASH WITHDRAWAL MUMBAI"]
    kotak = ("Sl. No.,Transaction Date,Value Date,Description,Chq / Ref No.,Amount,Dr / Cr,Balance\n"
             "1,03-10-2026,03-10-2026,UPI/AMIT SHAH/412345678901/movie,UPI-1,350.00,DR,4650.00\n"
             "2,04-10-2026,04-10-2026,IMPS-412345678901-ANIL KUMAR-SBIN-XXXXXXX1234-books,IMPS-1,500.00,CR,5150.00\n")
    k = parse_statement("kotak.csv", kotak.encode())
    assert [t.amount_pence for t in k.transactions] == [-35000, 50000]


def test_html_saved_as_xls():
    html = b"""<html><body><table>
    <tr><td>Axis Bank</td></tr>
    <tr><th>Tran Date</th><th>CHQNO</th><th>PARTICULARS</th><th>DR</th><th>CR</th><th>BAL</th></tr>
    <tr><td>05-10-2026</td><td></td><td>UPI/P2M/412345678901/SWIGGY/UPI/AXIS BANK</td><td>299.00</td><td></td><td>9701.00</td></tr>
    </table></body></html>"""
    r = parse_statement("statement.xls", html)
    assert r.transactions[0].description == "UPI SWIGGY" and r.transactions[0].amount_pence == -29900
    assert r.currency == "INR"  # Axis Bank named in the file


def test_upi_lines_from_each_bank():
    assert clean("UPI/P2A/412345678901/PREETI MISAL/SBI/rent") == "UPI PREETI MISAL RENT"
    assert clean("UPI/PREETI MISAL/412345678901/rent") == "UPI PREETI MISAL RENT"
    assert clean("UPI-ZOMATO LTD-ZOMATO.PAYU@AXISBANK-UTIB0000100-412345678901-UPI INTENT") == "UPI ZOMATO LTD"
    assert clean("POS 512345XXXXXX1234 DMART AVENUE") == "POS DMART AVENUE"
    assert clean("TESCO STORES 3021 CD 4821") == "TESCO STORES 3021 CD 4821"  # UK lines untouched


def test_rupee_account_kept_apart_from_pounds(client):
    from conftest import upload
    upload(client, "lloyds_export_1.csv", "lloyds_export_2.csv")
    r = client.post("/api/upload", files=[("files", ("hdfc.txt", HDFC_TXT.encode()))]).json()["results"][0]
    assert r["ok"], r
    accounts = {a["currency"]: a for a in client.get("/api/accounts").json()}
    assert set(accounts) == {"GBP", "INR"}
    assert [c["code"] for c in client.get("/api/currencies").json()] == ["GBP", "INR"]  # most transactions first
    gbp = client.get("/api/overview", params={"currency": "GBP"}).json()
    inr = client.get("/api/overview", params={"currency": "INR"}).json()
    assert inr["transaction_count"] == 6 and gbp["transaction_count"] > 100
    s = client.get("/api/summary/2026-10", params={"currency": "INR"}).json()
    assert s["salary_pence"] == 0 or s["income_pence"] >= 8500000
    cats = {c["category"]: c["spend_pence"] for c in s["categories"]}
    assert cats["Takeaways"] == 45600 and cats["Groceries"] == 34500 and cats["Cash"] == 200000
    assert all("£" not in h["text"] for h in s["highlights"]) and any("₹" in h["text"] for h in s["highlights"])
    txns = client.get("/api/transactions", params={"currency": "INR", "q": "rahul"}).json()
    assert txns[0]["category"] == "Eating out" and txns[0]["kind"] == "paid_back"
    chat = client.post("/api/chat", json={"question": "how much did I spend on takeaways?", "currency": "INR"}).json()
    assert "₹456" in chat["answer"] and "£" not in chat["answer"]


def test_account_currency_can_be_corrected(client):
    r = client.post("/api/upload", files=[("files", ("plain.csv", b"Date,Description,Amount\n2026-10-01,Corner shop,-3.50\n"))])
    acct = client.get("/api/accounts").json()[0]
    assert acct["currency"] == "GBP"
    fixed = client.patch(f"/api/accounts/{acct['id']}", json={"currency": "INR"}).json()
    assert fixed["currency"] == "INR"
    assert client.patch(f"/api/accounts/{acct['id']}", json={"currency": "XYZ"}).status_code == 400
    assert r.status_code == 200
