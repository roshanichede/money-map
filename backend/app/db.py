"""Database setup. SQLite by default; set DATABASE_URL for Postgres."""
import os

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker



def _normalise(url: str) -> str:
    """Hosts hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the psycopg driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = _normalise(os.environ.get("DATABASE_URL", "sqlite:///./moneymap.db"))

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# pool_pre_ping: hosted Postgres (e.g. Neon) closes idle connections; check before reuse.
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, _record):
    if DATABASE_URL.startswith("sqlite"):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


class Base(DeclarativeBase):
    pass


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _add_missing_columns(bind) -> None:
    """Columns added after a table first existed (create_all doesn't add columns to existing tables)."""
    from sqlalchemy import text

    added = {"accounts": [("currency", "VARCHAR(3) NOT NULL DEFAULT 'GBP'")]}
    insp = inspect(bind)
    for table, columns in added.items():
        if table not in insp.get_table_names():
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        for name, ddl in columns:
            if name not in have:
                with bind.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db(bind=None):
    from . import models  # noqa: F401  (register tables)
    from .migrate import migrate_v1

    bind = bind or engine
    tables = inspect(bind).get_table_names()
    needs_v1_migration = "users" not in tables and bool({"transactions", "transactions_v1", "uploads_v1"} & set(tables))
    if needs_v1_migration:
        migrate_v1(bind)
    else:
        Base.metadata.create_all(bind=bind)
    _add_missing_columns(bind)

    from sqlalchemy.orm import Session as _Session

    from .income import upgrade_existing_data

    with _Session(bind=bind) as session:
        upgrade_existing_data(session)
