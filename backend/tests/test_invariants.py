"""Product-level invariant tests for Document Again P0.

These are the promises the product makes. A failure here is blocking —
it must not be hidden behind UI completion.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DA_DB_PATH", tempfile.mkstemp(suffix=".db")[1])

from app import models as m  # noqa: E402
from app import services as svc  # noqa: E402
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.deps import db_session   # noqa: E402


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )

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
    return svc.create_project(db, key="DA", name="Document Again Dogfood")


@pytest.fixture()
def requirement(db, project):
    return svc.create_requirement(
        db, project_id=project.id, title="Approval history must be auditable"
    )


# ---------------------------------------------------------------------------
# 1. Confirmed revision cannot be modified
# ---------------------------------------------------------------------------


def test_confirmed_revision_is_immutable(db, project, requirement):
    artifact = svc.create_artifact(
        db, project_id=project.id, type=m.ArtifactType.UR, title="UR v1"
    )
    rev = artifact.revisions[0]
    svc.submit_for_review(db, rev.id)
    svc.confirm_revision(db, rev.id, actor="alice", comment="ok")

    with pytest.raises(svc.DomainError, match="immutable"):
        svc.update_revision_snapshot(db, rev.id, {"sections": ["changed"]})

    fresh = db.get(m.ArtifactRevision, rev.id)
    assert fresh.status == m.RevisionStatus.CONFIRMED
    assert fresh.snapshot == {}  # unchanged
    assert fresh.confirmed_by == "alice"


def test_confirming_again_is_rejected(db, project):
    artifact = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev = artifact.revisions[0]
    svc.confirm_revision(db, rev.id)
    with pytest.raises(svc.DomainError):
        svc.confirm_revision(db, rev.id)


# ---------------------------------------------------------------------------
# 2. Clone revision preserves parent relationship
# ---------------------------------------------------------------------------


def test_clone_preserves_ancestry(db, project):
    artifact = svc.create_artifact(
        db, project_id=project.id, type=m.ArtifactType.UR, title="UR",
        snapshot={"sections": ["overview"]},
    )
    rev1 = artifact.revisions[0]
    svc.confirm_revision(db, rev1.id)

    rev2 = svc.create_revision(db, artifact_id=artifact.id, based_on_revision_id=rev1.id)
    assert rev2.revision_number == 2
    assert rev2.based_on_revision_id == rev1.id
    assert rev2.status == m.RevisionStatus.DRAFT
    assert rev2.snapshot == {"sections": ["overview"]}  # cloned content
    assert db.get(m.ArtifactRevision, rev1.id).status == m.RevisionStatus.CONFIRMED


def test_clone_carries_latest_content_by_default(db, project):
    artifact = svc.create_artifact(
        db, project_id=project.id, type=m.ArtifactType.DR, title="DR",
        snapshot={"db": ["tbl_orders"]},
    )
    rev1 = artifact.revisions[0]
    rev2 = svc.create_revision(db, artifact_id=artifact.id)  # no explicit parent
    assert rev2.based_on_revision_id == rev1.id
    assert rev2.snapshot == {"db": ["tbl_orders"]}
    # original DRAFT is superseded by the newer draft pointer
    assert db.get(m.ArtifactRevision, rev1.id).status == m.RevisionStatus.SUPERSEDED


# ---------------------------------------------------------------------------
# 3+4. Baseline freezes revision bindings
# ---------------------------------------------------------------------------


def _confirmed_artifact(db, project, title, snapshot):
    artifact = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title=title, snapshot=snapshot)
    rev = artifact.revisions[0]
    svc.submit_for_review(db, rev.id)
    svc.confirm_revision(db, rev.id)
    return artifact, rev


def test_baseline_retains_bound_child_revision(db, project):
    _, rev1 = _confirmed_artifact(db, project, "DR", {"db": "v7"})
    dr_artifact = rev1.artifact

    baseline = svc.create_baseline(
        db, project_id=project.id, name="Baseline 1.0", artifact_revision_ids=[rev1.id]
    )
    frozen = baseline.bindings[0].artifact_revision_id
    assert frozen == rev1.id

    # Child artifact later becomes v8 (new revision, confirmed)
    rev2 = svc.create_revision(db, artifact_id=dr_artifact.id, snapshot={"db": "v8"})
    svc.submit_for_review(db, rev2.id)
    svc.confirm_revision(db, rev2.id)

    resolved = svc.resolve_baseline(db, baseline.id)
    assert resolved.bindings[0].artifact_revision_id == rev1.id  # still v7, not v8
    assert db.get(m.ArtifactRevision, frozen).snapshot["db"] == "v7"
    # P2: DR confirmation also freezes technical design atomically
    assert "technical_design" in db.get(m.ArtifactRevision, frozen).snapshot
    assert rev1.status == m.RevisionStatus.SUPERSEDED  # readable history


def test_baseline_rejects_unconfirmed_revisions(db, project):
    artifact = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.UR, title="UR")
    with pytest.raises(svc.DomainError, match="CONFIRMED"):
        svc.create_baseline(
            db, project_id=project.id, name="bad", artifact_revision_ids=[artifact.revisions[0].id]
        )


def test_new_child_revision_does_not_mutate_old_baseline(db, project, requirement):
    _, ur_rev = _confirmed_artifact(db, project, "UR", {"reqs": [requirement.code]})
    _, dr_rev = _confirmed_artifact(db, project, "DR", {"db": ["tbl_orders"]})

    baseline = svc.create_baseline(
        db, project_id=project.id, name="1.0",
        artifact_revision_ids=[ur_rev.id, dr_rev.id],
    )
    before = [b.artifact_revision_id for b in baseline.bindings]

    # CR-driven change: new DR revision after baseline
    cr = svc.create_change_request(
        db, project_id=project.id, requested_change="Add approval step",
        affected_semantic_ids=[requirement.code],
    )
    svc.implement_change_request(
        db, cr.id, artifact_revision_map={dr_rev.artifact_id: {"db": ["tbl_orders", "tbl_approval"]}}
    )

    resolved = svc.resolve_baseline(db, baseline.id)
    assert [b.artifact_revision_id for b in resolved.bindings] == before
    assert all(
        db.get(m.ArtifactRevision, b.artifact_revision_id).snapshot
        for b in resolved.bindings
    )


# ---------------------------------------------------------------------------
# 5. Trace links use stable semantic IDs
# ---------------------------------------------------------------------------


def test_trace_links_use_semantic_ids_only(db, project, requirement):
    _, rev = _confirmed_artifact(db, project, "DR", {})
    dr_sem = f"sec_{rev.id}"
    svc.ensure_semantic_object(
        db, project_id=project.id, semantic_id=dr_sem,
        object_type=m.SemanticObjectType.DOCUMENT_SECTION, display_name="DR section",
    )
    link = svc.create_trace_link(
        db, project_id=project.id, source_semantic_id=dr_sem,
        target_semantic_id=requirement.code,
        relation_type=m.TraceRelationType.DERIVED_FROM,
    )
    assert link.target_semantic_id == "REQ-0001"

    # Titles change; traces survive.
    requirement.title = "Renamed requirement"
    db.commit()
    impact = svc.impact_of(db, project.id, requirement.code)
    assert impact["upstream"][0]["semantic_id"] == dr_sem


def test_trace_rejects_unknown_semantic_ids(db, project):
    with pytest.raises(svc.DomainError, match="Unknown semantic object"):
        svc.create_trace_link(
            db, project_id=project.id, source_semantic_id="REQ-9999",
            target_semantic_id="tbl_ghost",
            relation_type=m.TraceRelationType.AFFECTS,
        )


# ---------------------------------------------------------------------------
# 6. Annotations remain bound to semantic objects
# ---------------------------------------------------------------------------


def test_annotation_semantic_anchor(db, project, requirement):
    annotation = svc.create_annotation(
        db, project_id=project.id, anchor_object_type="REQUIREMENT",
        anchor_semantic_id=requirement.code, content="Is audit retention 7 years?",
        type=m.AnnotationType.QUESTION, canvas_x=120, canvas_y=45,
    )
    assert annotation.anchor_semantic_id == "REQ-0001"
    svc.set_annotation_status(db, annotation.id, m.AnnotationStatus.RESOLVED)
    assert db.get(m.Annotation, annotation.id).status == m.AnnotationStatus.RESOLVED


def test_annotation_rejects_unknown_anchor(db, project):
    with pytest.raises(svc.DomainError, match="unknown semantic object"):
        svc.create_annotation(
            db, project_id=project.id, anchor_object_type="DB_TABLE",
            anchor_semantic_id="tbl_nowhere", content="?",
        )


# ---------------------------------------------------------------------------
# 7. Change Request creates/links new revision path
# ---------------------------------------------------------------------------


def test_change_request_revision_flow(db, project, requirement):
    artifact, rev1 = _confirmed_artifact(db, project, "UR", {"reqs": [requirement.code]})
    cr = svc.create_change_request(
        db, project_id=project.id, requested_change="Add one more approval step",
        affected_semantic_ids=[requirement.code], reason="Customer escalation",
    )
    assert cr.code == "CR-0001"
    result = svc.implement_change_request(
        db, cr.id,
        artifact_revision_map={artifact.id: {"reqs": [requirement.code], "steps": ["finance"]}},
    )
    assert result["change_request"].status == m.ChangeRequestStatus.IMPLEMENTED
    new_rev = result["spawned_revisions"][0]
    assert new_rev["revision_number"] == 2
    clone = db.get(m.ArtifactRevision, new_rev["revision_id"])
    assert clone.based_on_revision_id == rev1.id
    assert rev1.status == m.RevisionStatus.CONFIRMED  # old truth untouched
    traces = svc.impact_of(db, project.id, cr.code)
    assert traces["downstream"], "CR must trace to the revision it spawned"


# ---------------------------------------------------------------------------
# 8. Archived/superseded history remains readable
# ---------------------------------------------------------------------------


def test_superseded_history_readable(db, project):
    artifact, rev1 = _confirmed_artifact(db, project, "UR", {"v": 1})
    rev2 = svc.create_revision(db, artifact_id=artifact.id, snapshot={"v": 2})
    svc.confirm_revision(db, rev2.id)

    old = db.get(m.ArtifactRevision, rev1.id)
    assert old.status == m.RevisionStatus.SUPERSEDED
    assert old.snapshot["v"] == 1  # history preserved verbatim
    with pytest.raises(svc.DomainError, match="Illegal transition"):
        svc.transition_revision(db, old.id, m.RevisionStatus.DRAFT)


def test_illegal_transitions_rejected(db, project):
    artifact = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.NOTE, title="n")
    rev = artifact.revisions[0]
    svc.confirm_revision(db, rev.id)
    with pytest.raises(svc.DomainError, match="Illegal transition"):
        svc.transition_revision(db, rev.id, m.RevisionStatus.IN_REVIEW)


# ---------------------------------------------------------------------------
# 9. Database design objects are structured design data
# ---------------------------------------------------------------------------


def test_db_design_structured_model(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_core")
    tbl = svc.create_table(db, schema_id=schema.id, name="approval_history")
    fld = svc.create_field(
        db, table_id=tbl.id, name="approver_id", data_type="VARCHAR", length=64,
        foreign_key=True, reference="users.id", description="Who approved",
    )
    assert fld.semantic_id == "fld_approval_history_approver_id"
    svc.create_field(db, table_id=tbl.id, name="id", data_type="UUID", primary_key=True)

    dictionary = svc.data_dictionary(db, schema.id)
    assert any(row["field"] == "approver_id" and row["reference"] == "users.id" for row in dictionary)

    # tbl/fld registered as semantic objects → annotatable + traceable
    ann = svc.create_annotation(
        db, project_id=project.id, anchor_object_type="DB_FIELD",
        anchor_semantic_id="fld_approval_history_approver_id", content="Add index?",
    )
    assert ann.status == m.AnnotationStatus.OPEN


def test_db_relation_between_two_tables(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_c2")
    users = svc.create_table(db, schema_id=schema.id, name="users")
    svc.create_field(db, table_id=users.id, name="id", data_type="UUID", primary_key=True)
    hist = svc.create_table(db, schema_id=schema.id, name="history")
    svc.create_field(db, table_id=hist.id, name="user_id", data_type="UUID",
                     foreign_key=True, reference="users.id")
    rel = svc.create_relation(
        db, schema_id=schema.id,
        from_field_semantic_id="fld_history_user_id",
        to_field_semantic_id="fld_users_id",
    )
    assert rel.relation_type == "MANY_TO_ONE"


# ---------------------------------------------------------------------------
# 10. HTTP layer enforces the same rules (no bypass via API)
# ---------------------------------------------------------------------------


def test_api_rejects_edit_of_confirmed_revision(client, db, project):
    p = client.post("/api/projects", json={"key": "X1", "name": "X"}).json()
    a = client.post("/api/artifacts", json={
        "project_id": p["id"], "type": "UR", "title": "UR", "snapshot": {"a": 1},
    }).json()
    rev_id = a["revisions"][0]["id"]
    client.post(f"/api/revisions/{rev_id}/submit-for-review")
    client.post(f"/api/revisions/{rev_id}/confirm", json={"comment": "ok"})
    r = client.put(f"/api/revisions/{rev_id}/snapshot", json={"snapshot": {"a": 2}})
    assert r.status_code == 409
    assert "immutable" in r.json()["detail"]
    assert client.get(f"/api/revisions/{rev_id}").json()["snapshot"] == {"a": 1}


def test_api_health(client):
    assert client.get("/api/health").json()["status"] == "ok"
