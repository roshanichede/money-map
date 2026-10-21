"""MoneyMap API."""
import csv
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import chat
from .categories import CATEGORIES
from .db import get_session, init_db
from .importer import import_file
from .insights import (all_transactions, by_category, by_merchant, categorised_rate, compare_months, in_month,
                       months_overview, totals, txn_dict)
from .models import MerchantRule, Transaction, Upload
from .parsers import ParseError
from .recurring import detect_recurring

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="MoneyMap API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "chat_model": chat.MODEL if os.environ.get("ANTHROPIC_API_KEY") else None}


@app.get("/api/categories")
def categories():
    return CATEGORIES


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), session: Session = Depends(get_session)):
    results = []
    for f in files:
        content = await f.read()
        if len(content) > MAX_UPLOAD_BYTES:
            results.append({"filename": f.filename, "ok": False, "error": "File is larger than 10 MB."})
            continue
        try:
            up = import_file(session, f.filename or "statement", content)
        except ParseError as exc:
            session.rollback()
            results.append({"filename": f.filename, "ok": False, "error": str(exc)})
            continue
        results.append({"filename": up.filename, "ok": True, "format": up.source_format, "rows_read": up.rows_read,
                        "rows_added": up.rows_added, "duplicates_skipped": up.duplicates_skipped,
                        "reconciled": up.reconciled, "reconciliation_note": up.reconciliation_note})
    return {"results": results}


@app.post("/api/demo")
def load_demo(session: Session = Depends(get_session)):
    """Load the synthetic sample statements so the app can be tried without real data."""
    sample_dir = Path(__file__).resolve().parent.parent / "sample_data"
    results = []
    for name in ("lloyds_export_1.csv", "lloyds_export_2.csv", "lloyds_statement_2026-09.pdf"):
        path = sample_dir / name
        if path.exists():
            up = import_file(session, name, path.read_bytes())
            results.append({"filename": name, "rows_added": up.rows_added, "reconciled": up.reconciled})
    return {"results": results}


@app.get("/api/uploads")
def uploads(session: Session = Depends(get_session)):
    rows = session.scalars(select(Upload).order_by(Upload.uploaded_at.desc()))
    return [{"id": u.id, "filename": u.filename, "format": u.source_format, "uploaded_at": u.uploaded_at.isoformat(),
             "rows_read": u.rows_read, "rows_added": u.rows_added, "duplicates_skipped": u.duplicates_skipped,
             "reconciled": u.reconciled, "reconciliation_note": u.reconciliation_note} for u in rows]


@app.get("/api/overview")
def overview(session: Session = Depends(get_session)):
    txns = all_transactions(session)
    return {"months": months_overview(txns), "transaction_count": len(txns),
            "categorised_rate": round(categorised_rate(txns), 3)}


@app.get("/api/summary/{month}")
def summary(month: str, session: Session = Depends(get_session)):
    txns = all_transactions(session)
    mt = in_month(txns, month)
    if not mt:
        raise HTTPException(404, f"No transactions in {month}.")
    months = sorted({o["month"] for o in months_overview(txns)})
    idx = months.index(month)
    comparison = compare_months(txns, month, months[idx - 1]) if idx > 0 else None
    return {"month": month, **totals(mt), "categories": by_category(mt), "merchants": by_merchant(mt, 8),
            "categorised_rate": round(categorised_rate(mt), 3), "comparison": comparison}


@app.get("/api/transactions")
def transactions(month: str | None = None, category: str | None = None, q: str | None = None,
                 session: Session = Depends(get_session)):
    txns = all_transactions(session)
    if month:
        txns = in_month(txns, month)
    if category:
        txns = [t for t in txns if t.category == category]
    if q:
        ql = q.lower()
        txns = [t for t in txns if ql in t.description.lower() or ql in t.merchant.lower()]
    return [txn_dict(t) for t in reversed(txns)]


class CategoryUpdate(BaseModel):
    category: str
    apply_to_merchant: bool = True


@app.patch("/api/transactions/{txn_id}")
def set_category(txn_id: int, body: CategoryUpdate, session: Session = Depends(get_session)):
    if body.category not in CATEGORIES:
        raise HTTPException(400, f"Unknown category. Use one of: {', '.join(CATEGORIES)}")
    txn = session.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(404, "Transaction not found.")
    txn.category, txn.category_source = body.category, "manual"
    updated = 1
    if body.apply_to_merchant:
        rule = session.scalar(select(MerchantRule).where(MerchantRule.merchant_key == txn.merchant_key))
        if rule:
            rule.category = body.category
        else:
            session.add(MerchantRule(merchant_key=txn.merchant_key, category=body.category))
        for other in session.scalars(select(Transaction).where(Transaction.merchant_key == txn.merchant_key,
                                                               Transaction.id != txn.id)):
            if other.category_source != "manual":
                other.category, other.category_source = body.category, "learned"
                updated += 1
    session.commit()
    return {"updated": updated, "merchant": txn.merchant, "category": body.category}


@app.get("/api/recurring")
def recurring(session: Session = Depends(get_session)):
    rows = detect_recurring(all_transactions(session))
    active = [r for r in rows if r["active"]]
    return {"items": rows, "active_monthly_total_pence": sum(r["monthly_cost_pence"] for r in active)}


class Question(BaseModel):
    question: str


@app.post("/api/chat")
def ask(body: Question, session: Session = Depends(get_session)):
    question = body.question.strip()[:500]
    if not question:
        raise HTTPException(400, "Ask a question.")
    return chat.ask(question, all_transactions(session))


@app.get("/api/export")
def export(session: Session = Depends(get_session)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "description", "merchant", "category", "type", "amount_gbp", "balance_gbp", "account"])
    for t in all_transactions(session):
        w.writerow([t.date.isoformat(), t.description, t.merchant, t.category, t.txn_type,
                    f"{t.amount_pence / 100:.2f}",
                    "" if t.balance_pence is None else f"{t.balance_pence / 100:.2f}", t.account])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=moneymap-export.csv"})


@app.delete("/api/data")
def delete_all(session: Session = Depends(get_session)):
    counts = {"transactions": session.query(Transaction).count(), "uploads": session.query(Upload).count()}
    session.execute(delete(Transaction))
    session.execute(delete(MerchantRule))
    session.execute(delete(Upload))
    session.commit()
    return {"deleted": counts}
