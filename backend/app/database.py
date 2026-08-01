import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DATA_DIR is the parent folder holding both master.db and the projects/
# subfolder (one SQLite file, plus an evidence/ subfolder, per project).
# Defaults to backend/data for local dev — unset by default, so local
# `uvicorn` behaves exactly as before. Set it to override (e.g. a mounted
# volume when deployed).
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(BASE_DIR, "data")
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)

MASTER_DB_URL = f"sqlite:///{os.path.join(DATA_DIR, 'master.db')}"

MasterBase = declarative_base()
ProjectBase = declarative_base()

master_engine = create_engine(
    MASTER_DB_URL, connect_args={"check_same_thread": False}
)
MasterSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=master_engine
)

_project_engines = {}
_project_sessions = {}

# Additive column patches, applied on top of `create_all` so pre-existing
# SQLite files (created before a schema patch) pick up new nullable columns
# without a full migration tool. Never used to change/remove existing columns
# — see ADR-0001 and the rebuild prompt section 2 for why this mirrors
# PM-Again's pattern exactly.
MASTER_COLUMN_PATCHES: dict[str, dict[str, str]] = {
    "projects": {
        "storage_quota_bytes": "INTEGER DEFAULT 5368709120",
        "storage_warning_thresholds": "TEXT DEFAULT '[70, 85, 95, 100]'",
    },
}
PROJECT_COLUMN_PATCHES: dict[str, dict[str, str]] = {}


def ensure_columns(engine, table_columns: dict[str, dict[str, str]]):
    with engine.connect() as conn:
        for table, columns in table_columns.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, coltype in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}"))
        conn.commit()


def project_db_path(slug: str) -> str:
    return os.path.join(PROJECTS_DIR, f"{slug}.db")


def project_evidence_dir(slug: str) -> str:
    path = os.path.join(PROJECTS_DIR, slug, "evidence")
    os.makedirs(path, exist_ok=True)
    return path


def evidence_storage_root_dir() -> str:
    """Root for FilesystemEvidenceStorage (ADR-0002) — plain DATA_DIR, not
    DATA_DIR/evidence: object keys already start with `evidence/...`
    (`evidence/{slug}/{result_id}/...`) so the same key scheme works
    unchanged against R2 (see backend/app/storage/). Returning DATA_DIR
    here (rather than DATA_DIR/evidence) avoids a doubled `evidence/
    evidence/...` path on disk. Distinct from project_evidence_dir(),
    which is HYB-0's own spike-scoped evidence storage and is left
    untouched by this ADR."""
    os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DIR


def project_db_exists(slug: str) -> bool:
    return os.path.exists(project_db_path(slug))


def get_project_engine(slug: str):
    if slug not in _project_engines:
        url = f"sqlite:///{project_db_path(slug)}"
        # timeout=30: SQLite serializes writers — a concurrent evidence
        # upload's commit (see routers/evidence.py's quota race handling)
        # should wait for the other writer's commit rather than raising
        # "database is locked" under ordinary concurrency (Python's
        # sqlite3 default timeout is 5s, too tight for that).
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
        ProjectBase.metadata.create_all(bind=engine)
        ensure_columns(engine, PROJECT_COLUMN_PATCHES)
        _project_engines[slug] = engine
        _project_sessions[slug] = sessionmaker(
            autocommit=False, autoflush=False, bind=engine
        )
    return _project_engines[slug]


def open_project_session(slug: str):
    """Returns a new Session for `slug`, for use outside the FastAPI
    dependency-injection flow (e.g. from within another router's handler).
    Caller is responsible for closing it."""
    get_project_engine(slug)
    return _project_sessions[slug]()


def dispose_project_engine(slug: str) -> None:
    """Closes and drops the cached engine/sessionmaker for `slug` — required
    before deleting its SQLite file, otherwise a stale cached connection
    could still be used (or block the file delete on some platforms)."""
    engine = _project_engines.pop(slug, None)
    _project_sessions.pop(slug, None)
    if engine:
        engine.dispose()


def get_master_db():
    db = MasterSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_project_db(slug: str):
    """FastAPI dependency: `slug` is auto-resolved from the path parameter
    of the same name on the endpoint that depends on this."""
    get_project_engine(slug)
    session_local = _project_sessions[slug]
    db = session_local()
    try:
        yield db
    finally:
        db.close()
