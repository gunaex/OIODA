import logging
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
        # Running Code Generator's "PJ" prefix — nullable, a project without
        # one just keeps typing task/function codes by hand.
        "project_code": "TEXT",
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
        # Progress Matrix (Yotei-Jisseki): generalises linked_task_id to any
        # entity. Additive and nullable — linked_task_id is untouched, so the
        # existing Gantt bar chart keeps querying exactly what it always did.
        "linked_entity_type": "TEXT",
        "linked_entity_id": "INTEGER",
    },
    "documents": {
        "google_drive_file_id": "TEXT",  # reserved — no OAuth flow yet
    },
    # Delivery Mode (HUMAN / HUMAN-in-LOOP). Additive and defaulted so every
    # estimate created before this feature keeps its original numbers.
    "effort_estimate_config": {
        "hil_leverage_json": "TEXT",
        "hil_price_discount_percent": "REAL DEFAULT 35",
        "show_delivery_mode_in_client_docs": "BOOLEAN DEFAULT 0",
        "hil_restricted": "BOOLEAN DEFAULT 0",
    },
    "effort_estimates": {
        "delivery_mode": "TEXT DEFAULT 'human'",
        "effort_multiplier_applied": "REAL DEFAULT 1.0",
        "man_days_human": "REAL",
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


def backfill_gantt_entity_links(engine):
    """Progress Matrix migration: every pre-existing gantt_items row that had
    a linked_task_id gets the equivalent generalised link, so the new
    linked_entity_type/id columns describe the whole table from day one and
    the Progress Matrix doesn't have to special-case "old rows".

    Idempotent: the WHERE clause only matches rows not yet backfilled, so this
    is a no-op on every run after the first. linked_task_id itself is never
    read out of, changed, or cleared."""
    with engine.connect() as conn:
        existing_tables = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        if "gantt_items" not in existing_tables:
            return
        conn.execute(
            text(
                "UPDATE gantt_items "
                "SET linked_entity_type = 'task', linked_entity_id = linked_task_id "
                "WHERE linked_task_id IS NOT NULL AND linked_entity_type IS NULL"
            )
        )
        conn.commit()


def backfill_delivery_mode(engine):
    """Delivery Mode migration: an estimate saved before the feature existed
    was, by definition, a HUMAN estimate. ALTER TABLE ... DEFAULT already
    fills delivery_mode and effort_multiplier_applied for existing rows; this
    fills man_days_human, which has no default because it isn't a constant —
    for a HUMAN estimate it equals the man-days already stored.

    Idempotent: only touches rows still holding NULL."""
    with engine.connect() as conn:
        existing_tables = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        if "effort_estimates" not in existing_tables:
            return
        conn.execute(
            text(
                "UPDATE effort_estimates SET man_days_human = calculated_man_days "
                "WHERE man_days_human IS NULL AND calculated_man_days IS NOT NULL"
            )
        )
        conn.execute(text("UPDATE effort_estimates SET delivery_mode = 'human' WHERE delivery_mode IS NULL"))
        conn.execute(
            text("UPDATE effort_estimates SET effort_multiplier_applied = 1.0 WHERE effort_multiplier_applied IS NULL")
        )
        conn.commit()


# (table, column) pairs the Running Code Generator needs to be unique so a
# manually-typed or imported code can never silently collide with one another
# code names the same thing.
UNIQUE_CODE_COLUMNS = [("tasks", "task_code"), ("functions", "function_code")]


def enforce_unique_codes(engine):
    """Running Code Generator migration: makes task_code/function_code unique
    per project, in two steps.

    1. De-duplicate first. A code column had no constraint before this, so a
       project created earlier could already hold two rows sharing a code
       (typed by hand, or from a round-tripped import). Renaming the second
       and later occurrences (appending -DUP2, -DUP3, ...) is necessary before
       a UNIQUE index can be added at all — it would otherwise fail outright
       with an existing conflict, and CREATE INDEX gives no natural place to
       report per-row problems the way the import path does.
    2. Add a partial UNIQUE index (NULL and '' excluded, since those aren't
       "the same code" — they're "no code yet"). CREATE INDEX IF NOT EXISTS is
       idempotent, so this is a no-op on every run after the first.

    Runs on every project DB open, same as the other backfills in this file.
    """
    with engine.connect() as conn:
        existing_tables = {
            row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        for table, column in UNIQUE_CODE_COLUMNS:
            if table not in existing_tables:
                continue

            duplicate_codes = [
                row[0]
                for row in conn.execute(
                    text(
                        f"SELECT {column} FROM {table} "
                        f"WHERE {column} IS NOT NULL AND {column} != '' "
                        f"GROUP BY {column} HAVING COUNT(*) > 1"
                    )
                )
            ]
            for code in duplicate_codes:
                row_ids = [
                    row[0]
                    for row in conn.execute(
                        text(f"SELECT id FROM {table} WHERE {column} = :code ORDER BY id"), {"code": code}
                    )
                ]
                # The first (oldest) row keeps the code unchanged; every later
                # one is renamed. Rare in practice — this exists so the
                # migration can't fail outright on data from before codes
                # were enforced, not because it's an expected case.
                for suffix, row_id in enumerate(row_ids[1:], start=2):
                    conn.execute(
                        text(f"UPDATE {table} SET {column} = :new_code WHERE id = :row_id"),
                        {"new_code": f"{code}-DUP{suffix}", "row_id": row_id},
                    )
                    logging.getLogger("database").warning(
                        "De-duplicated %s.%s %r on row id=%s -> %r (unique index migration)",
                        table, column, code, row_id, f"{code}-DUP{suffix}",
                    )

            index_name = f"ux_{table}_{column}"
            conn.execute(
                text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table}({column}) "
                    f"WHERE {column} IS NOT NULL AND {column} != ''"
                )
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
        backfill_gantt_entity_links(engine)
        backfill_delivery_mode(engine)
        enforce_unique_codes(engine)
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
