import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DATA_DIR is the parent folder holding both master.db and the projects/
# subfolder (one SQLite file per project). Defaults to backend/data for
# local dev — unset by default, so `npm run dev` / local `uvicorn` behave
# exactly as before. Set it to override (e.g. a mounted volume when deployed).
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
# without a full migration tool. Never used to change/remove existing columns.
MASTER_COLUMN_PATCHES = {
    "projects": {
        "project_type": "TEXT DEFAULT 'simple'",
        "project_category": "TEXT",
        "notification_email": "TEXT",  # reserved — no email sending wired up yet
        "archived": "BOOLEAN DEFAULT 0",
    },
    "users": {
        "must_change_password": "BOOLEAN DEFAULT 0",
    },
}
PROJECT_COLUMN_PATCHES = {
    "functions": {
        "module": "TEXT",
        "priority": "TEXT",
        "scope_class": "TEXT",
        "complexity": "TEXT",
        "pd_ba": "REAL",
        "pd_ux": "REAL",
        "pd_fe": "REAL",
        "pd_be": "REAL",
        "pd_int_data": "REAL",
        "pd_qa": "REAL",
        "pd_devops": "REAL",
        "pd_total": "REAL",
        "performance_class": "TEXT",
        "target_option_a": "TEXT",
        "target_option_b": "TEXT",
        "target_option_c": "TEXT",
        "performance_note": "TEXT",
        "price_thb": "REAL",
        "commercial_note": "TEXT",
    },
    "tasks": {
        "phase": "TEXT",
    },
    "gantt_items": {
        "phase": "TEXT",
        "google_calendar_event_id": "TEXT",  # reserved — no OAuth flow yet
    },
    "documents": {
        "google_drive_file_id": "TEXT",  # reserved — no OAuth flow yet
    },
}

# Old (guessed) phase enum -> real company phase enum, per
# ClaudeCode_PhaseModel_DocTemplates_Spec.md. Applied to any row still
# holding an old value; a no-op once every row has been migrated.
PHASE_ENUM_MIGRATION = {
    "PU-PT": "PU",
    "IFT": "ST",
    "BCT": "ST",
    "UAT": "UT",
    # UR, DR, IP are unchanged; DN/TR/MA are new phases with no old equivalent.
}


def ensure_columns(engine, table_columns: dict[str, dict[str, str]]):
    with engine.connect() as conn:
        for table, columns in table_columns.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for name, coltype in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}"))
        conn.commit()


def migrate_phase_values(engine, tables: list[str]):
    """Idempotent: rewrites any row still holding an old phase value to its
    new equivalent. Safe to run on every connect — once migrated, the WHERE
    clause matches nothing."""
    with engine.connect() as conn:
        existing_tables = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        for table in tables:
            if table not in existing_tables:
                continue
            for old, new in PHASE_ENUM_MIGRATION.items():
                conn.execute(
                    text(f"UPDATE {table} SET phase = :new WHERE phase = :old"),
                    {"new": new, "old": old},
                )
        conn.commit()


def project_db_path(slug: str) -> str:
    return os.path.join(PROJECTS_DIR, f"{slug}.db")


def project_db_exists(slug: str) -> bool:
    return os.path.exists(project_db_path(slug))


def get_project_engine(slug: str):
    if slug not in _project_engines:
        url = f"sqlite:///{project_db_path(slug)}"
        engine = create_engine(url, connect_args={"check_same_thread": False})
        ProjectBase.metadata.create_all(bind=engine)
        ensure_columns(engine, PROJECT_COLUMN_PATCHES)
        migrate_phase_values(engine, ["functions", "tasks", "gantt_items", "documents"])
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
