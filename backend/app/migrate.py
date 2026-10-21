"""One-off upgrade of a v1 database (single user, no accounts) to the current schema.

Nothing is lost: the database file is copied to moneymap.v1-backup.db first, v1 rows are read into memory,
the old tables are dropped and recreated, and the rows go back in under the local user, grouped into
accounts by the account number the v1 importer stored. Duplicate keys are recalculated per account.
Also copes with a half-finished earlier attempt (tables already renamed to *_v1).
"""
import hashlib
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .accounts import create_account
from .auth import LOCAL_EMAIL
from .categories import categorise
from .models import MerchantRule, Transaction, Upload, User

V1_TABLES = ("uploads", "transactions", "merchant_rules")


def _as_date(v):
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _as_dt(v):
    return v if isinstance(v, datetime) or v is None else datetime.fromisoformat(str(v))


def _backup(bind) -> None:
    db_path = bind.url.database
    if bind.url.get_backend_name() == "sqlite" and db_path and db_path != ":memory:" and Path(db_path).exists():
        backup = Path(db_path).with_name(Path(db_path).stem + ".v1-backup.db")
        if not backup.exists():
            shutil.copy2(db_path, backup)


def migrate_v1(bind) -> None:
    from .db import Base
    from .transfers import link_transfers

    _backup(bind)
    existing = set(inspect(bind).get_table_names())
    with bind.connect() as conn:
        def rows(name):
            for candidate in (name, f"{name}_v1"):
                if candidate in existing:
                    return [dict(r) for r in conn.execute(text(f'SELECT * FROM "{candidate}" ORDER BY id')).mappings()]
            return []

        old_uploads, old_txns, old_rules = rows("uploads"), rows("transactions"), rows("merchant_rules")
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for name in V1_TABLES:
            for candidate in (name, f"{name}_v1"):
                if candidate in existing:
                    conn.execute(text(f'DROP TABLE "{candidate}"'))
        conn.commit()
        conn.execute(text("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(bind=bind)

    old_txns.sort(key=lambda r: (r["upload_id"], r["id"]))
    with Session(bind=bind) as s:
        user = User(email=LOCAL_EMAIL, name="You")
        s.add(user)
        s.flush()
        accounts = {}
        for number in sorted({(r.get("account") or "") for r in old_txns}):
            accounts[number] = create_account(s, user.id, number=number or None,
                                              bank="Lloyds" if number else None, account_type="current")
        upload_account = {}
        for r in old_txns:
            upload_account.setdefault(r["upload_id"], accounts[r.get("account") or ""].id)

        upload_ids = {}
        for u in old_uploads:
            new = Upload(user_id=user.id, account_id=upload_account.get(u["id"]), filename=u["filename"],
                         source_format=u["source_format"], uploaded_at=_as_dt(u["uploaded_at"]),
                         rows_read=u["rows_read"], rows_added=u["rows_added"],
                         duplicates_skipped=u["duplicates_skipped"], reconciled=u["reconciled"],
                         reconciliation_note=u["reconciliation_note"])
            s.add(new)
            s.flush()
            upload_ids[u["id"]] = new.id

        seen: dict[int, Counter] = defaultdict(Counter)
        for r in old_txns:
            if r["upload_id"] not in upload_ids:
                continue
            acct_id = accounts[r.get("account") or ""].id
            d = _as_date(r["date"])
            if r["balance_pence"] is not None:
                base = f"{acct_id}|bal|{d.isoformat()}|{r['amount_pence']}|{r['balance_pence']}"
            else:
                base = f"{acct_id}|desc|{d.isoformat()}|{r['amount_pence']}|{' '.join(r['description'].upper().split())}"
            seen[r["upload_id"]][base] += 1
            key = hashlib.sha256(f"{base}|#{seen[r['upload_id']][base]}".encode()).hexdigest()
            category = r["category"]
            if r["category_source"] == "rule":  # re-run the rules: v2 knows about card repayments etc.
                category = categorise(r["description"], r["merchant_key"], r["txn_type"], r["amount_pence"])
            s.add(Transaction(user_id=user.id, account_id=acct_id, upload_id=upload_ids[r["upload_id"]], date=d,
                              description=r["description"], merchant=r["merchant"], merchant_key=r["merchant_key"],
                              txn_type=r["txn_type"], amount_pence=r["amount_pence"], balance_pence=r["balance_pence"],
                              category=category, category_source=r["category_source"], dedupe_key=key))
        for r in old_rules:
            s.add(MerchantRule(user_id=user.id, merchant_key=r["merchant_key"], category=r["category"]))
        s.flush()
        link_transfers(s, user.id)
        s.commit()
