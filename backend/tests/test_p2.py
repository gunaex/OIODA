"""P2 tests — technical-design authority upgrades.

Covers atomic auto-snapshot confirmation, reproducible export, flow / API /
architecture structured models, decision promotion, and identity.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DA_DB_PATH", tempfile.mkstemp(suffix=".db")[1])

from app import models as m  # noqa: E402
from app import services as svc  # noqa: E402
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.deps import db_session  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("pragma foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db):
    app.dependency_overrides[db_session] = lambda: (yield db)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def project(db):
    return svc.create_project(db, key="DA2", name="P2 Project")


@pytest.fixture()
def requirement(db, project):
    return svc.create_requirement(db, project_id=project.id, title="2-level approval required")


def _dr_in_review(db, project):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev = art.revisions[0]
    svc.submit_for_review(db, rev.id)
    return art, rev


# ---------------------------------------------------------------------------
# P2-B atomic auto-snapshot confirmation
# ---------------------------------------------------------------------------


def test_confirm_dr_auto_snapshots_technical_design(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_core")
    tbl = svc.create_table(db, schema_id=schema.id, name="orders")
    svc.create_field(db, table_id=tbl.id, name="id", data_type="UUID", primary_key=True)

    _, rev = _dr_in_review(db, project)
    rev, _ = svc.confirm_revision(db, rev.id, actor="alice", comment="ok")

    td = rev.snapshot["technical_design"]
    assert "sch_core" in td["db_schemas"]
    assert td["db_schemas"]["sch_core"]["tables"]["tbl_orders"]["fields"]["fld_orders_id"]["primary_key"] is True


def test_snapshot_failure_rolls_back_confirmation(db, project, monkeypatch):
    _, rev = _dr_in_review(db, project)

    def boom(db_, project_id):
        raise RuntimeError("simulated snapshot failure")

    monkeypatch.setattr(svc, "snapshot_technical_design", boom)

    with pytest.raises(RuntimeError, match="simulated"):
        svc.confirm_revision(db, rev.id, actor="alice")

    db.expire_all()
    fresh = db.get(m.ArtifactRevision, rev.id)
    assert fresh.status == m.RevisionStatus.IN_REVIEW  # no half-confirmed state
    assert fresh.confirmed_by is None
    confs = db.execute(select(m.Confirmation)).scalars().all()
    assert len(confs) == 0  # no confirmation record survived


def test_atomic_confirm_is_all_or_nothing(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_a")
    svc.create_table(db, schema_id=schema.id, name="t1")
    _, rev = _dr_in_review(db, project)
    rev, conf = svc.confirm_revision(db, rev.id, actor="bob", comment="ok", evidence={"r": "x"})
    assert rev.status == m.RevisionStatus.CONFIRMED
    assert conf.confirmed_by == "bob"
    assert "technical_design" in rev.snapshot
