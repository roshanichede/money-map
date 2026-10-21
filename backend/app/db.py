"""Database setup. SQLite by default; set DATABASE_URL for Postgres."""
import os

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./moneymap.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
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
