"""MoneyMap API. Every route works on the signed-in user's data only (see auth.py)."""
import calendar
from datetime import date
import csv
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import chat
from .accounts import TYPE_LABELS
from .auth import current_user, find_or_create, internal_only, login_mode
from .passwords import MIN_LENGTH, check_password, hash_password, throttle
from .categories import CATEGORIES
from .db import get_session, init_db
from .importer import AccountChoiceError, import_file
from .insights import (all_transactions, by_category, by_merchant, categorised_rate, compare_months, earnings,
                       highlights, in_month, months_overview, totals, txn_dict)
from . import capture, learning, teach
from .money import CURRENCIES, set_currency
from .models import ACCOUNT_TYPES, Account, CaptureKey, Credential, Dismissed, MerchantRule, Rule, Transaction, Upload, User
from .parsers import ParseError
from .recurring import detect_recurring
from .transfers import link_transfers, unlink_account

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"
SAMPLE_FILES = ("lloyds_export_1.csv", "lloyds_export_2.csv", "lloyds_statement_2026-09.pdf",
                "lloyds_savings.csv", "lloyds_credit_card.csv")


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="MoneyMap API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


def _currencies(session: Session, user: User) -> list[str]:
    """The user's currencies, the one with most transactions first."""
    rows = session.execute(select(Account.currency, func.count(Transaction.id))
                           .outerjoin(Transaction, Transaction.account_id == Account.id)
                           .where(Account.user_id == user.id).group_by(Account.currency)).all()
    return [c for c, _ in sorted(rows, key=lambda r: -r[1])]


def _scope(session: Session, user: User, account_id: int | None, currency: str | None):
    """Transactions for one account, or for all accounts in one currency, and set that currency for formatting."""
    _own_account(session, user, account_id)
    if account_id is not None:
        code = session.get(Account, account_id).currency
    else:
        mine = _currencies(session, user)
        code = currency if currency in mine else (mine[0] if mine else "GBP")
    set_currency(code)
    return all_transactions(session, user.id, account_id, None if account_id is not None else code)


def _own_account(session: Session, user: User, account_id: int | None) -> int | None:
    if account_id is None:
        return None
    acct = session.get(Account, account_id)
    if acct is None or acct.user_id != user.id:
        raise HTTPException(404, "Account not found.")
    return account_id


@app.get("/api/health")
def health():
    return {"ok": True, "chat_model": chat.MODEL if os.environ.get("ANTHROPIC_API_KEY") else None,
            "login_mode": login_mode()}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"email": None if user.email == "local@moneymap" else user.email, "name": user.name,
            "login_mode": login_mode()}


# ---------- email + password accounts (called by the Next.js server only) ----------

class SignUp(BaseModel):
    email: str
    password: str
    name: str = ""


class SignIn(BaseModel):
    email: str
    password: str


def _email(raw: str) -> str:
    email = raw.strip().lower()
    if len(email) > 254 or "@" not in email or "." not in email.split("@")[-1] or " " in email:
        raise HTTPException(400, "Enter a valid email address.")
    return email


@app.post("/api/account/signup", dependencies=[Depends(internal_only)])
def signup(body: SignUp, session: Session = Depends(get_session)):
    email = _email(body.email)
    if len(body.password) < MIN_LENGTH:
        raise HTTPException(400, f"Use at least {MIN_LENGTH} characters for your password.")
    if len(body.password) > 200:
        raise HTTPException(400, "That password is too long.")
    existing = session.scalar(select(User).where(User.email == email))
    if existing:
        has_password = session.scalar(select(Credential).where(Credential.user_id == existing.id))
        raise HTTPException(409, "There's already an account with this email. Sign in instead."
                            if has_password else
                            "This email already signs in with Google. Use “Continue with Google”.")
    user = find_or_create(session, email, body.name.strip()[:255] or email.split("@")[0])
    session.add(Credential(user_id=user.id, password_hash=hash_password(body.password)))
    session.commit()
    return {"email": user.email, "name": user.name}


@app.post("/api/account/signin", dependencies=[Depends(internal_only)])
def signin(body: SignIn, session: Session = Depends(get_session)):
    email = body.email.strip().lower()
    if throttle.blocked(email):
        raise HTTPException(429, "Too many attempts. Wait 15 minutes and try again.")
    user = session.scalar(select(User).where(User.email == email))
    cred = user and session.scalar(select(Credential).where(Credential.user_id == user.id))
    if not cred or not check_password(body.password, cred.password_hash):
        throttle.fail(email)
        raise HTTPException(401, "That email and password don't match.")
    throttle.clear(email)
    return {"email": user.email, "name": user.name}


@app.get("/api/currencies")
def currencies(user: User = Depends(current_user), session: Session = Depends(get_session)):
    """The currencies this person has accounts in, most used first, with their symbols."""
    return [{"code": c, "symbol": CURRENCIES[c]} for c in _currencies(session, user)]


@app.get("/api/categories")
def categories():
    return CATEGORIES


def _upload_result(up: Upload, session: Session) -> dict:
    acct = session.get(Account, up.account_id) if up.account_id else None
    return {"filename": up.filename, "ok": True, "format": up.source_format, "rows_read": up.rows_read,
            "rows_added": up.rows_added, "duplicates_skipped": up.duplicates_skipped,
            "reconciled": up.reconciled, "reconciliation_note": up.reconciliation_note,
            "account": acct.name if acct else None, "account_id": acct.id if acct else None,
            "account_match": getattr(up, "account_match", None),
            "transfers_matched": getattr(up, "transfers_matched", 0)}


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), account_id: int | None = Form(None),
                 new_account_type: str | None = Form(None), new_account_name: str | None = Form(None),
                 user: User = Depends(current_user), session: Session = Depends(get_session)):
    if new_account_type and new_account_type not in ACCOUNT_TYPES:
        raise HTTPException(400, f"Account type must be one of: {', '.join(ACCOUNT_TYPES)}")
    results = []
    for f in files:
        content = await f.read()
        if len(content) > MAX_UPLOAD_BYTES:
            results.append({"filename": f.filename, "ok": False, "error": "File is larger than 10 MB."})
            continue
        try:
            up = import_file(session, user.id, f.filename or "statement", content, account_id=account_id,
                             new_account_type=new_account_type, new_account_name=new_account_name)
        except (ParseError, AccountChoiceError) as exc:
            session.rollback()
            results.append({"filename": f.filename, "ok": False, "error": str(exc)})
            continue
        results.append(_upload_result(up, session))
        if new_account_name or new_account_type:  # a new account is created once, then reused for the batch
            account_id = up.account_id
            new_account_name = new_account_type = None
    return {"results": results}


@app.post("/api/demo")
def load_demo(user: User = Depends(current_user), session: Session = Depends(get_session)):
    """Load synthetic statements (current account, savings, credit card) so the app can be tried safely."""
    results = []
    for name in SAMPLE_FILES:
        path = SAMPLE_DIR / name
        if path.exists():
            results.append(_upload_result(import_file(session, user.id, name, path.read_bytes()), session))
    return {"results": results}


@app.get("/api/uploads")
def uploads(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.scalars(select(Upload).where(Upload.user_id == user.id).order_by(Upload.uploaded_at.desc()))
    names = {a.id: a.name for a in session.scalars(select(Account).where(Account.user_id == user.id))}
    return [{"id": u.id, "filename": u.filename, "format": u.source_format, "uploaded_at": u.uploaded_at.isoformat(),
             "account": names.get(u.account_id), "rows_read": u.rows_read, "rows_added": u.rows_added,
             "duplicates_skipped": u.duplicates_skipped, "reconciled": u.reconciled,
             "reconciliation_note": u.reconciliation_note} for u in rows]


# ---------- accounts ----------

def _account_dict(session: Session, a: Account) -> dict:
    last_with_balance = session.scalars(select(Transaction).where(
        Transaction.account_id == a.id, Transaction.balance_pence.is_not(None))
        .order_by(Transaction.date.desc(), Transaction.id.desc()).limit(1)).first()
    count, first, last = session.execute(select(func.count(), func.min(Transaction.date), func.max(Transaction.date))
                                         .where(Transaction.account_id == a.id)).one()
    transfers = session.scalar(select(func.count()).select_from(Transaction).where(
        Transaction.account_id == a.id, Transaction.transfer_pair_id.is_not(None)))
    set_currency(a.currency)
    return {"id": a.id, "name": a.name, "bank": a.bank, "account_type": a.account_type, "currency": a.currency,
            "type_label": TYPE_LABELS.get(a.account_type, "Account"), "last4": a.last4,
            "balance_pence": last_with_balance.balance_pence if last_with_balance else None,
            "balance_date": last_with_balance.date.isoformat() if last_with_balance else None,
            "transaction_count": count, "first_date": first.isoformat() if first else None,
            "last_date": last.isoformat() if last else None, "transfers_matched": transfers}


@app.get("/api/accounts")
def accounts(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.id))
    return [_account_dict(session, a) for a in rows]


class AccountUpdate(BaseModel):
    name: str | None = None
    account_type: str | None = None
    currency: str | None = None


@app.patch("/api/accounts/{account_id}")
def update_account(account_id: int, body: AccountUpdate, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    _own_account(session, user, account_id)
    acct = session.get(Account, account_id)
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(400, "Give the account a name.")
        acct.name = body.name.strip()[:120]
    if body.account_type is not None:
        if body.account_type not in ACCOUNT_TYPES:
            raise HTTPException(400, f"Account type must be one of: {', '.join(ACCOUNT_TYPES)}")
        acct.account_type = body.account_type
    if body.currency is not None:
        if body.currency not in CURRENCIES:
            raise HTTPException(400, f"Currency must be one of: {', '.join(CURRENCIES)}")
        acct.currency = body.currency
    session.commit()
    return _account_dict(session, acct)


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    _own_account(session, user, account_id)
    unlink_account(session, account_id)
    n = session.scalar(select(func.count()).select_from(Transaction).where(Transaction.account_id == account_id))
    session.execute(delete(Transaction).where(Transaction.account_id == account_id))
    session.execute(delete(Upload).where(Upload.account_id == account_id))
    session.execute(delete(CaptureKey).where(CaptureKey.account_id == account_id))
    session.execute(delete(Account).where(Account.id == account_id))
    session.commit()
    return {"deleted_transactions": n}


# ---------- insights ----------

@app.get("/api/overview")
def overview(account_id: int | None = None, currency: str | None = None, user: User = Depends(current_user),
             session: Session = Depends(get_session)):
    txns = _scope(session, user, account_id, currency)
    return {"months": months_overview(txns), "transaction_count": len(txns),
            "categorised_rate": round(categorised_rate(txns), 3)}


@app.get("/api/summary/{month}")
def summary(month: str, account_id: int | None = None, currency: str | None = None, user: User = Depends(current_user),
            session: Session = Depends(get_session)):
    txns = _scope(session, user, account_id, currency)
    mt = in_month(txns, month)
    if not mt:
        raise HTTPException(404, f"No transactions in {month}.")
    months = sorted({o["month"] for o in months_overview(txns)})
    idx = months.index(month)
    comparison = compare_months(txns, month, months[idx - 1]) if idx > 0 else None
    transfers = -sum(t.amount_pence for t in mt if t.transfer_pair_id is not None and t.amount_pence < 0)
    last_day = max(t.date for t in mt)
    unfinished = month == months[-1] and last_day.day < calendar.monthrange(last_day.year, last_day.month)[1] - 2
    return {"month": month, **totals(mt), "categories": by_category(mt), "merchants": by_merchant(mt, 8),
            "categorised_rate": round(categorised_rate(mt), 3), "comparison": comparison,
            "transfers_out_pence": transfers, "highlights": highlights(txns, month, comparison, unfinished)}


@app.get("/api/earnings")
def earnings_view(account_id: int | None = None, currency: str | None = None, user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
    return earnings(_scope(session, user, account_id, currency))


@app.get("/api/transactions")
def transactions(month: str | None = None, category: str | None = None, q: str | None = None,
                 account_id: int | None = None, currency: str | None = None, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    txns = _scope(session, user, account_id, currency)
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
    apply_to_merchant: bool = True  # the app sends False and then offers the ways to apply it more widely


@app.patch("/api/transactions/{txn_id}")
def set_category(txn_id: int, body: CategoryUpdate, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    if body.category not in CATEGORIES:
        raise HTTPException(400, f"Unknown category. Use one of: {', '.join(CATEGORIES)}")
    txn = session.get(Transaction, txn_id)
    if txn is None or txn.user_id != user.id:
        raise HTTPException(404, "Transaction not found.")
    txn.category, txn.category_source = body.category, "manual"
    updated = 1
    if body.apply_to_merchant:
        rule = session.scalar(select(MerchantRule).where(MerchantRule.user_id == user.id,
                                                         MerchantRule.merchant_key == txn.merchant_key))
        if rule:
            rule.category = body.category
        else:
            session.add(MerchantRule(user_id=user.id, merchant_key=txn.merchant_key, category=body.category))
        for other in session.scalars(select(Transaction).where(
                Transaction.user_id == user.id, Transaction.merchant_key == txn.merchant_key,
                Transaction.id != txn.id)):
            if other.category_source not in ("manual", "transfer"):
                other.category, other.category_source = body.category, "learned"
                updated += 1
    session.commit()
    options = [] if body.apply_to_merchant else learning.scope_options(session, user.id, txn, body.category)
    return {"updated": updated, "merchant": txn.merchant, "category": body.category, "options": options}


# ---------- teaching MoneyMap ----------

class RuleSpec(BaseModel):
    payee: str = ""
    word: str = ""
    max_pence: int | None = None
    merchant_key: str = ""


class NewRule(BaseModel):
    spec: RuleSpec
    category: str
    taught_via: str = "edit"


def _clean_spec(s: RuleSpec) -> "learning.Spec":
    up = lambda x: " ".join(x.upper().split())[:120]  # noqa: E731
    if s.max_pence is not None and s.max_pence <= 0:
        raise HTTPException(400, "The amount limit must be more than £0.")
    return learning.Spec(payee=up(s.payee), word=up(s.word)[:60], max_pence=s.max_pence, merchant_key=up(s.merchant_key))


@app.get("/api/rules")
def rules(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return learning.list_rules(session, user.id)


@app.post("/api/rules/preview")
def rule_preview(body: NewRule, user: User = Depends(current_user), session: Session = Depends(get_session)):
    if body.category not in CATEGORIES:
        raise HTTPException(400, "Unknown category.")
    return learning.preview(session, user.id, _clean_spec(body.spec), body.category)


@app.post("/api/rules")
def add_rule(body: NewRule, user: User = Depends(current_user), session: Session = Depends(get_session)):
    try:
        return learning.save_rule(session, user.id, _clean_spec(body.spec), body.category,
                                  body.taught_via if body.taught_via in ("edit", "question", "chat") else "edit")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/rules/{rule_id}")
def remove_rule(rule_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)):
    try:
        return {"moved": learning.delete_rule(session, user.id, rule_id)}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/questions")
def questions(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return learning.questions(session, user.id)


class Dismiss(BaseModel):
    key: str


@app.post("/api/questions/dismiss")
def dismiss_question(body: Dismiss, user: User = Depends(current_user), session: Session = Depends(get_session)):
    learning.dismiss(session, user.id, body.key)
    return {"ok": True}


@app.get("/api/recurring")
def recurring(account_id: int | None = None, currency: str | None = None, user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    rows = detect_recurring(_scope(session, user, account_id, currency))
    active = [r for r in rows if r["active"]]
    return {"items": rows, "active_monthly_total_pence": sum(r["monthly_cost_pence"] for r in active)}


class Question(BaseModel):
    question: str
    account_id: int | None = None
    currency: str | None = None


@app.post("/api/chat")
def ask(body: Question, user: User = Depends(current_user), session: Session = Depends(get_session)):
    question = body.question.strip()[:500]
    if not question:
        raise HTTPException(400, "Ask a question.")
    txns = _scope(session, user, body.account_id, body.currency)  # also sets the currency for wording
    taught = teach.proposal(question, session, user.id)  # "garba is entertainment" teaches instead of asks
    if taught:
        return {"answer": taught["answer"], "source": "rules", "guardrail": "not_used", "intent": "teach",
                "facts": {}, "evidence": [], "proposal": taught["proposal"]}
    return chat.ask(question, txns)


# ---------- your data ----------

@app.get("/api/export")
def export(user: User = Depends(current_user), session: Session = Depends(get_session)):
    names = {a.id: a.name for a in session.scalars(select(Account).where(Account.user_id == user.id))}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "account", "description", "merchant", "category", "type", "amount_gbp", "balance_gbp"])
    for t in all_transactions(session, user.id):
        w.writerow([t.date.isoformat(), names.get(t.account_id, ""), t.description, t.merchant, t.category,
                    t.txn_type, f"{t.amount_pence / 100:.2f}",
                    "" if t.balance_pence is None else f"{t.balance_pence / 100:.2f}"])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=moneymap-export.csv"})


@app.delete("/api/data")
def delete_all(user: User = Depends(current_user), session: Session = Depends(get_session)):
    counts = {
        "transactions": session.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id)),
        "accounts": session.scalar(select(func.count()).select_from(Account).where(Account.user_id == user.id)),
    }
    for model in (Transaction, MerchantRule, Rule, Dismissed, Upload, CaptureKey, Account):  # the login itself is kept
        session.execute(delete(model).where(model.user_id == user.id))
    session.commit()
    return {"deleted": counts}


@app.post("/api/transfers/relink")
def relink(user: User = Depends(current_user), session: Session = Depends(get_session)):
    pairs = link_transfers(session, user.id)
    session.commit()
    return {"pairs": pairs}


# ---------- live capture from the phone ----------

class NewCaptureLink(BaseModel):
    account_id: int
    source: str


def _link_dict(session: Session, k: CaptureKey) -> dict:
    acct = session.get(Account, k.account_id)
    return {"id": k.id, "account_id": k.account_id, "account": acct.name if acct else None,
            "currency": acct.currency if acct else None, "source": k.source,
            "created_at": k.created_at.isoformat(), "uses": k.uses,
            "last_used": k.last_used.isoformat() if k.last_used else None}


@app.get("/api/capture-links")
def capture_links(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.scalars(select(CaptureKey).where(CaptureKey.user_id == user.id, CaptureKey.revoked.is_(False))
                           .order_by(CaptureKey.created_at))
    return [_link_dict(session, k) for k in rows]


@app.post("/api/capture-links")
def create_capture_link(body: NewCaptureLink, user: User = Depends(current_user),
                        session: Session = Depends(get_session)):
    _own_account(session, user, body.account_id)
    if body.source not in capture.SOURCES:
        raise HTTPException(400, "Source must be applepay or sms.")
    token = capture.new_token()
    key = CaptureKey(user_id=user.id, account_id=body.account_id, source=body.source,
                     token_hash=capture.token_hash(token))
    session.add(key)
    session.commit()
    # The full link is only ever shown now; afterwards only its hash exists.
    return {**_link_dict(session, key), "path": f"/api/capture/{token}"}


@app.delete("/api/capture-links/{link_id}")
def revoke_capture_link(link_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    key = session.get(CaptureKey, link_id)
    if key is None or key.user_id != user.id:
        raise HTTPException(404, "Link not found.")
    key.revoked = True
    session.commit()
    return {"ok": True}


@app.post("/api/capture/{token}")
async def capture_payment(token: str, request: Request, session: Session = Depends(get_session)):
    """Called by the phone's Shortcuts automation. The secret link is the only credential."""
    key = capture.find_key(session, token)
    if key is None:
        raise HTTPException(404, "Not found.")
    if not capture.limit.allow(key.token_hash):
        raise HTTPException(429, "Too many payments sent in the last hour.")
    raw = (await request.body())[:8000]
    data: dict = {}
    if "json" in request.headers.get("content-type", ""):
        try:
            import json as _json

            parsed = _json.loads(raw or b"{}")
            data = parsed if isinstance(parsed, dict) else {"sms": str(parsed)}
        except ValueError:
            data = {"sms": raw.decode("utf-8", "replace")}
    else:
        form_like = raw.decode("utf-8", "replace")
        data = {"sms": form_like}
    acct = session.get(Account, key.account_id)
    if data.get("check"):  # "Check link" on the setup page: confirms the link works, records nothing
        return {"ok": True, "recorded": None, "linked": acct.name}
    set_currency(acct.currency)
    today = date.today()
    try:
        if key.source == "applepay" or data.get("merchant") is not None:
            when, desc, amount = capture.from_apple_pay(str(data.get("merchant", "")), str(data.get("amount", "")), today)
        else:
            text = str(data.get("sms") or data.get("message") or data.get("text") or "")
            when, desc, amount = capture.from_sms(text, today)
    except (capture.NotAPayment, ParseError) as exc:
        return {"ok": True, "recorded": None, "ignored": str(exc)}
    t = capture.record(session, key, when, desc, amount)
    from .money import fmt_money

    return {"ok": True, "recorded": {"date": t.date.isoformat(), "merchant": t.merchant,
                                     "amount": fmt_money(t.amount_pence), "category": t.category,
                                     "account": acct.name}}
