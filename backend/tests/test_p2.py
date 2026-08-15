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


# ---------------------------------------------------------------------------
# P2-H account identity
# ---------------------------------------------------------------------------


def test_actor_identity_resolution(client, db, project):
    svc.ensure_semantic_object(db, project_id=project.id, semantic_id="REQ-0001",
                               object_type=m.SemanticObjectType.REQUIREMENT, display_name="req")
    r = client.post("/api/annotations", json={
        "project_id": project.id, "anchor_object_type": "REQUIREMENT",
        "anchor_semantic_id": "REQ-0001", "content": "hi",
    }, headers={"X-Account-Id": "acc-123", "X-Actor-Name": "Alice", "X-Tenant-Id": "t-1"})
    assert r.status_code == 201
    ann = db.execute(select(m.Annotation)).scalars().one()
    assert ann.actor_id == "acc-123"
    assert ann.created_by == "Alice"
    actor_row = db.get(m.ActorIdentity, "acc-123")
    # In local mode the header is a trusted shortcut, not Account Again-validated.
    assert actor_row is not None and actor_row.source == "LOCAL" and actor_row.tenant_id == "t-1"


# ---------------------------------------------------------------------------
# P2-I/J reproducible export
# ---------------------------------------------------------------------------


def test_historical_reexport_uses_baseline_snapshot(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_h")
    tbl = svc.create_table(db, schema_id=schema.id, name="orders")
    svc.create_field(db, table_id=tbl.id, name="id", data_type="UUID", primary_key=True)
    _, rev = _dr_in_review(db, project)
    rev, _ = svc.confirm_revision(db, rev.id, actor="alice")  # auto-snapshot with id only

    # change live DB to v2 (add field)
    svc.create_field(db, table_id=tbl.id, name="status", data_type="VARCHAR")

    csv_bytes, _, _ = svc.export_revision(db, rev.id, "csv")
    text = csv_bytes.decode()
    assert "id" in text
    assert "status" not in text  # historical export must not contain the v2 field

    baseline = svc.create_baseline(db, project_id=project.id, name="1.0", artifact_revision_ids=[rev.id])
    zip_bytes = svc.export_design_package(db, baseline.id)
    assert zip_bytes[:2] == b"PK"  # zip magic


def test_pdf_export(db, project):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev = art.revisions[0]
    svc.save_document(db, revision_id=rev.id, sections=[{
        "id": "s1", "heading": "Overview",
        "content": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}]},
    }])
    svc.confirm_revision(db, rev.id)
    pdf, _, _ = svc.export_revision(db, rev.id, "pdf")
    assert pdf[:4] == b"%PDF"


def test_flow_and_architecture_models(db, project):
    flow = svc.create_flow(db, project_id=project.id, name="Purchase Approval", semantic_id="flow_purchase_approval")
    s1 = svc.add_flow_step(db, flow_id=flow.id, name="Submit", step_type="START")
    s2 = svc.add_flow_step(db, flow_id=flow.id, name="Manager Review", step_type="APPROVAL")
    t = svc.add_flow_transition(db, flow_id=flow.id, from_step_semantic_id=s1.semantic_id, to_step_semantic_id=s2.semantic_id, label="submit")
    assert t.semantic_id == "flow_transition_flow_step_submit__flow_step_manager_review"
    # flow step semantic ids registered
    so = db.execute(select(m.SemanticObject).where(m.SemanticObject.semantic_id == s1.semantic_id)).scalar_one()
    assert so.object_type == m.SemanticObjectType.PROCESS_STEP

    d = svc.create_architecture_diagram(db, project_id=project.id, name="System", semantic_id="arch_system")
    n1 = svc.add_architecture_node(db, diagram_id=d.id, name="API", semantic_id="svc_order", node_type="SERVICE")
    n2 = svc.add_architecture_node(db, diagram_id=d.id, name="DB", semantic_id="db_order", node_type="DATABASE")
    svc.add_architecture_edge(db, diagram_id=d.id, from_node_semantic_id=n1.semantic_id, to_node_semantic_id=n2.semantic_id, label="SQL")
    so2 = db.execute(select(m.SemanticObject).where(m.SemanticObject.semantic_id == n1.semantic_id)).scalar_one()
    assert so2.object_type == m.SemanticObjectType.ARCHITECTURE_NODE


def test_promote_annotation_to_decision(db, project, requirement):
    ann = svc.create_annotation(db, project_id=project.id, anchor_object_type="REQUIREMENT",
                                anchor_semantic_id=requirement.code, content="Use 3-level approval")
    result = svc.promote_annotation(db, annotation_id=ann.id, to_kind="decision", actor="bob")
    assert result["kind"] == "decision"
    assert result["provenance"]["annotation_id"] == ann.id
    d = db.execute(select(m.Decision).where(m.Decision.semantic_id == result["code"])).scalar_one()
    assert d.content == "Use 3-level approval"
    # provenance recorded on the semantic object
    so = db.execute(select(m.SemanticObject).where(m.SemanticObject.semantic_id == result["code"])).scalar_one()
    assert so.metadata_json["provenance"]["source"] == "annotation"
    # original annotation resolved
    assert db.get(m.Annotation, ann.id).status == m.AnnotationStatus.RESOLVED
