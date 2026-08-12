"""
Conductor Again — Database Layer
Dual SQLite: master.db (global) + projects/{slug}.db (per-project).
Mirrors PM Again pattern.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "./data")
MASTER_DB_PATH = os.path.join(DATA_DIR, "master.db")

# Ensure data directories
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(os.path.join(DATA_DIR, "projects")).mkdir(parents=True, exist_ok=True)

# ── Master DB ──────────────────────────────────────────────
master_engine = create_engine(
    f"sqlite:///{MASTER_DB_PATH}",
    connect_args={"check_same_thread": False},
)
MasterSessionLocal = sessionmaker(bind=master_engine, autocommit=False, autoflush=False)
MasterBase = declarative_base()

# ── Project DBs ────────────────────────────────────────────
_project_engines: dict[str, any] = {}
ProjectBase = declarative_base()


def get_project_engine(slug: str):
    """Get or create engine for a project database."""
    if slug not in _project_engines:
        db_path = os.path.join(DATA_DIR, "projects", f"{slug}.db")
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        ProjectBase.metadata.create_all(bind=engine)
        _project_engines[slug] = engine
    return _project_engines[slug]


def get_project_session(slug: str) -> Session:
    engine = get_project_engine(slug)
    return Session(bind=engine, autocommit=False, autoflush=False)


def dispose_project_engine(slug: str):
    if slug in _project_engines:
        _project_engines[slug].dispose()
        del _project_engines[slug]


def dispose_all_engines():
    master_engine.dispose()
    for engine in list(_project_engines.values()):
        engine.dispose()
    _project_engines.clear()


# ── FastAPI Dependencies ───────────────────────────────────

def get_master_db():
    db = MasterSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_project_db(slug: str):
    db = get_project_session(slug)
    try:
        yield db
    finally:
        db.close()


# ── Startup ────────────────────────────────────────────────

def ensure_master_db():
    """Create master tables on startup."""
    MasterBase.metadata.create_all(bind=master_engine)


# SQLite foreign key enforcement
@event.listens_for(master_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
