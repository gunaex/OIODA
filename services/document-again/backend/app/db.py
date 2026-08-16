"""Database session management for Document Again.

``DATABASE_URL`` selects the production-capable target (e.g. PostgreSQL);
SQLite remains the local-development fallback. No secrets are committed.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATA_DIR = Path(os.environ.get("DA_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(os.environ.get("DA_DB_PATH", DATA_DIR / "document-again.db"))

DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{DB_PATH}"

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # SQLite: enforce foreign keys
        dbapi_conn.execute("pragma foreign_keys=ON")
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
