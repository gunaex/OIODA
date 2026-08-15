"""P1 integration + invariant tests for Document Again.

Covers the P1 acceptance matrix: document workspace, review workflow,
DB/ERD, data dictionary, revision diff, traceability, impact, change
request, and cross-feature behaviour. P0 invariants remain covered in
test_invariants.py and must not regress.
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
    return svc.create_project(db, key="DA1", name="P1 Project")


@pytest.fixture()
def requirement(db, project):
    return svc.create_requirement(db, project_id=project.id, title="2-level approval required")


def _confirmed_artifact(db, project, type_, title, snapshot=None):
    art = svc.create_artifact(db, project_id=project.id, type=type_, title=title, snapshot=snapshot)
    rev = art.revisions[0]
    svc.submit_for_review(db, rev.id)
    svc.confirm_revision(db, rev.id, actor="alice", comment="ok")
    return art, rev


# ---------------------------------------------------------------------------
# P1 Document
# ---------------------------------------------------------------------------


def test_draft_document_edit_and_reopen(db, project):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.UR, title="UR")
    rev = art.revisions[0]
    sections = [
        {"id": f"docsec_{art.id}_0", "heading": "Overview", "blocks": [{"kind": "paragraph", "text": "hello"}]},
    ]
    svc.save_document(db, revision_id=rev.id, sections=sections)
    doc = svc.get_document(db, rev.id)
    assert doc["sections"][0]["heading"] == "Overview"
    # reopen — persists
    doc2 = svc.get_document(db, rev.id)
    assert doc2["sections"][0]["blocks"][0]["text"] == "hello"


def test_document_section_stable_id(db, project):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev = art.revisions[0]
    sid = f"docsec_{art.id}_0"
    svc.save_document(db, revision_id=rev.id, sections=[{"id": sid, "heading": "A", "blocks": []}])
    # edit heading + blocks, id must not change
    svc.save_document(db, revision_id=rev.id, sections=[{"id": sid, "heading": "Renamed", "blocks": [{"kind": "paragraph", "text": "x"}]}])
    doc = svc.get_document(db, rev.id)
    assert doc["sections"][0]["id"] == sid
    # registered as a semantic object
    so = db.execute(
        svc.select(m.SemanticObject).where(m.SemanticObject.semantic_id == sid)
    ).scalar_one_or_none()
    assert so is not None and so.object_type == m.SemanticObjectType.DOCUMENT_SECTION


def test_confirmed_document_read_only(db, project):
    art, rev = _confirmed_artifact(db, project, m.ArtifactType.UR, "UR")
    with pytest.raises(svc.DomainError, match="immutable"):
        svc.save_document(db, revision_id=rev.id, sections=[{"id": "x", "heading": "h", "blocks": []}])


# ---------------------------------------------------------------------------
# P1 Review workflow
# ---------------------------------------------------------------------------


def test_review_submit_comment_resolve_confirm(db, project):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.UR, title="UR")
    rev = art.revisions[0]
    sec = f"docsec_{art.id}_0"
    svc.save_document(db, revision_id=rev.id, sections=[{"id": sec, "heading": "S1", "blocks": []}])

    assert svc.submit_for_review(db, rev.id).status == m.RevisionStatus.IN_REVIEW

    ann = svc.create_annotation(
        db, project_id=project.id, anchor_object_type="DOCUMENT_SECTION",
        anchor_semantic_id=sec, content="clarify retention", type=m.AnnotationType.QUESTION,
        artifact_revision_id=rev.id,
    )
    assert ann.anchor_semantic_id == sec
    assert svc.set_annotation_status(db, ann.id, m.AnnotationStatus.RESOLVED).status == m.AnnotationStatus.RESOLVED

    rev, conf = svc.confirm_revision(db, rev.id, actor="bob", comment="approved", evidence={"review": "walkthrough"})
    assert rev.status == m.RevisionStatus.CONFIRMED
    assert conf.confirmed_by == "bob" and conf.evidence == {"review": "walkthrough"}


def test_semantic_context(db, project, requirement):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev = art.revisions[0]
    sid = f"docsec_{art.id}_0"
    svc.save_document(db, revision_id=rev.id, sections=[{"id": sid, "heading": "S1", "blocks": []}])
    svc.submit_for_review(db, rev.id)
    svc.confirm_revision(db, rev.id, actor="alice", comment="ok")
    ctx = svc.semantic_context(db, project.id, sid)
    assert ctx["object_type"] == "DOCUMENT_SECTION"
    assert ctx["confirmed"] is True
    assert ctx["revision"]["confirmed_by"] == "alice"


# ---------------------------------------------------------------------------
# P1 DB designer / ERD / dictionary
# ---------------------------------------------------------------------------


def test_table_field_crud_and_stable_ids(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_core")
    tbl = svc.create_table(db, schema_id=schema.id, name="orders")
    f = svc.create_field(db, table_id=tbl.id, name="status", data_type="VARCHAR")
    # rename table keeps field semantic id stable
    svc.rename_table(db, tbl.id, "order_items")
    db.expire_all()
    assert db.get(m.DatabaseField, f.id).semantic_id == "fld_orders_status"
    # update field
    svc.update_field(db, f.id, data_type="ENUM", primary_key=False)
    assert db.get(m.DatabaseField, f.id).data_type == "ENUM"
    # delete field then table
    svc.delete_field(db, f.id)
    assert db.get(m.DatabaseField, f.id) is None
    svc.delete_table(db, tbl.id)
    assert db.get(m.DatabaseTable, tbl.id) is None


def test_fk_relation_and_delete(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_r")
    users = svc.create_table(db, schema_id=schema.id, name="users")
    svc.create_field(db, table_id=users.id, name="id", data_type="UUID", primary_key=True)
    hist = svc.create_table(db, schema_id=schema.id, name="history")
    svc.create_field(db, table_id=hist.id, name="user_id", data_type="UUID", foreign_key=True, reference="users.id")
    rel = svc.create_relation(db, schema_id=schema.id, from_field_semantic_id="fld_history_user_id", to_field_semantic_id="fld_users_id")
    assert rel.relation_type == "MANY_TO_ONE"
    svc.delete_relation(db, rel.id)
    assert db.get(m.DatabaseRelation, rel.id) is None


def test_erd_layout_is_not_schema_truth(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_e")
    tbl = svc.create_table(db, schema_id=schema.id, name="orders")
    svc.save_erd_layout(db, schema.id, {"tbl_orders": {"x": 10, "y": 20}})
    # move node
    svc.save_erd_layout(db, schema.id, {"tbl_orders": {"x": 999, "y": 888}})
    assert svc.get_erd_layout(db, schema.id)["tbl_orders"] == {"x": 999, "y": 888}
    # semantic identity + schema unchanged
    assert db.get(m.DatabaseTable, tbl.id).semantic_id == "tbl_orders"
    so = db.execute(svc.select(m.SemanticObject).where(m.SemanticObject.semantic_id == "tbl_orders")).scalar_one()
    assert so.object_type == m.SemanticObjectType.DB_TABLE


def test_dictionary_from_canonical_schema(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_d")
    tbl = svc.create_table(db, schema_id=schema.id, name="orders")
    svc.create_field(db, table_id=tbl.id, name="id", data_type="UUID", primary_key=True)
    svc.create_field(db, table_id=tbl.id, name="status", data_type="VARCHAR", length=16, description="order status")
    d = svc.data_dictionary(db, schema.id)
    assert len(d) == 2
    row = next(r for r in d if r["field"] == "status")
    assert row["length"] == 16 and row["description"] == "order status"
    # update model → dictionary reflects (no second copy)
    f = db.execute(svc.select(m.DatabaseField).where(m.DatabaseField.semantic_id == "fld_orders_status")).scalar_one()
    svc.update_field(db, f.id, data_type="ENUM")
    d2 = svc.data_dictionary(db, schema.id)
    assert next(r for r in d2 if r["field"] == "status")["data_type"] == "ENUM"


# ---------------------------------------------------------------------------
# P1 Diff
# ---------------------------------------------------------------------------


def test_text_diff(db):
    d = svc.text_diff("a\nb", "a\nc\nb")
    assert any(c["op"] == "insert" and c["lines"] == ["c"] for c in d)


def test_semantic_db_diff(db):
    a = {"tables": {"tbl_orders": {"name": "orders", "fields": {"fld_orders_status": {"name": "status", "data_type": "VARCHAR"}, "fld_orders_tmp": {"name": "tmp", "data_type": "INT"}}}}, "relations": {}}
    b = {"tables": {"tbl_orders": {"name": "orders", "fields": {"fld_orders_status": {"name": "status", "data_type": "ENUM"}}}, "tbl_approval": {"name": "approval_history", "fields": {}}}, "relations": {}}
    d = svc.semantic_db_diff(a, b)
    kinds = {(c["object"], c["kind"], c.get("attribute")) for c in d}
    assert ("TABLE", "ADDED", None) in kinds
    assert ("FIELD", "REMOVED", None) in kinds
    assert ("FIELD", "CHANGED", "data_type") in kinds


def test_document_diff_stable_objects(db, project):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev1 = art.revisions[0]
    svc.save_document(db, revision_id=rev1.id, sections=[{"id": "s1", "heading": "A", "blocks": []}, {"id": "s2", "heading": "B", "blocks": []}])
    svc.confirm_revision(db, rev1.id)
    rev2 = svc.create_revision(db, artifact_id=art.id, snapshot=dict(rev1.snapshot))
    svc.save_document(db, revision_id=rev2.id, sections=[{"id": "s1", "heading": "A changed", "blocks": []}, {"id": "s3", "heading": "C", "blocks": []}])
    diff = svc.document_diff(db, rev1.id, rev2.id)
    kinds = {(c["object"], c["kind"], c["semantic_id"]) for c in diff}
    assert ("SECTION", "REMOVED", "s2") in kinds
    assert ("SECTION", "ADDED", "s3") in kinds
    assert ("SECTION", "CHANGED", "s1") in kinds


def test_revision_diff_includes_database(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_x")
    tbl = svc.create_table(db, schema_id=schema.id, name="orders")
    svc.create_field(db, table_id=tbl.id, name="id", data_type="UUID", primary_key=True)

    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev1 = art.revisions[0]
    svc.snapshot_database_into_revision(db, rev1.id, schema.id)
    svc.confirm_revision(db, rev1.id)

    svc.create_field(db, table_id=tbl.id, name="status", data_type="VARCHAR")
    rev2 = svc.create_revision(db, artifact_id=art.id, snapshot=dict(rev1.snapshot))
    svc.snapshot_database_into_revision(db, rev2.id, schema.id)

    diff = svc.revision_diff(db, rev1.id, rev2.id)
    assert any(c["object"] == "FIELD" and c["kind"] == "ADDED" and c["semantic_id"] == "fld_orders_status" for c in diff["database_diff"])


# ---------------------------------------------------------------------------
# P1 Trace / Impact
# ---------------------------------------------------------------------------


def _link(db, project, src, dst, rel=m.TraceRelationType.DERIVED_FROM, rev_ctx=None):
    return svc.create_trace_link(db, project_id=project.id, source_semantic_id=src, target_semantic_id=dst, relation_type=rel, revision_context=rev_ctx)


def test_trace_incoming_outgoing_and_revision_context(db, project, requirement):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev = art.revisions[0]
    sid = f"docsec_{art.id}_0"
    svc.save_document(db, revision_id=rev.id, sections=[{"id": sid, "heading": "S", "blocks": []}])
    _link(db, project, sid, requirement.code, rev_ctx=f"r{rev.revision_number}")
    g = svc.trace_graph(db, project.id)
    assert any(e["source"] == sid and e["target"] == requirement.code and e["revision_context"] == f"r{rev.revision_number}" for e in g["edges"])
    imp = svc.impact_of(db, project.id, requirement.code)
    assert any(u["semantic_id"] == sid for u in imp["upstream"])


def test_impact_direct_and_bounded_transitive(db, project, requirement):
    # build chain: REQ -> a -> b -> c -> d  (REQ DERIVED_FROM a, a IMPLEMENTS b, ...)
    sids = ["sec_a", "sec_b", "sec_c", "sec_d"]
    for sid in sids:
        svc.ensure_semantic_object(db, project_id=project.id, semantic_id=sid, object_type=m.SemanticObjectType.DOCUMENT_SECTION, display_name=sid)
    _link(db, project, sids[0], requirement.code)
    _link(db, project, sids[1], sids[0], rel=m.TraceRelationType.IMPLEMENTS)
    _link(db, project, sids[2], sids[1], rel=m.TraceRelationType.AFFECTS)
    _link(db, project, sids[3], sids[2], rel=m.TraceRelationType.REFERENCES)

    analysis = svc.impact_analysis(db, project.id, requirement.code, max_depth=2)
    # direct upstream: sec_a
    assert any(u["semantic_id"] == "sec_a" for u in analysis["direct"]["upstream"])
    # bounded transitive upstream paths from REQ: REQ <- a, REQ <- a <- b (depth 2)
    depths = {len(p) for p in analysis["paths"]["upstream"]}
    assert max(depths) <= 2
    # path explanation carries relation chain
    assert any(p[0]["semantic_id"] == "sec_a" and p[0]["relation"] == "DERIVED_FROM" for p in analysis["paths"]["upstream"])


def test_impact_no_invented_dependency(db, project):
    svc.ensure_semantic_object(db, project_id=project.id, semantic_id="ghost", object_type=m.SemanticObjectType.DOCUMENT_SECTION, display_name="ghost")
    analysis = svc.impact_analysis(db, project.id, "ghost")
    assert analysis["direct"]["downstream"] == []
    assert analysis["direct"]["upstream"] == []
    assert analysis["paths"]["downstream"] == [] and analysis["paths"]["upstream"] == []


def test_unknown_trace_object_rejected(db, project):
    with pytest.raises(svc.DomainError, match="Unknown semantic object"):
        svc.create_trace_link(db, project_id=project.id, source_semantic_id="REQ-9999", target_semantic_id="tbl_ghost", relation_type=m.TraceRelationType.AFFECTS)


# ---------------------------------------------------------------------------
# P1 Change request
# ---------------------------------------------------------------------------


def test_cr_impact_linking_and_new_revision_preserves_baseline(db, project, requirement):
    ur_art, ur_rev = _confirmed_artifact(db, project, m.ArtifactType.UR, "UR")
    dr_art, dr_rev = _confirmed_artifact(db, project, m.ArtifactType.DR, "DR")

    baseline = svc.create_baseline(db, project_id=project.id, name="1.0", artifact_revision_ids=[ur_rev.id, dr_rev.id])
    before = [b.artifact_revision_id for b in baseline.bindings]

    cr = svc.create_change_request(
        db, project_id=project.id, requested_change="Add one more approval step",
        affected_semantic_ids=[requirement.code], reason="Customer escalation",
    )
    detail = svc.change_request_detail(db, cr.id)
    assert detail["affected"][0]["semantic_id"] == requirement.code
    assert "impact" in detail

    result = svc.implement_change_request(db, cr.id, artifact_revision_map={dr_art.id: {"note": "add director review"}})
    new_rev = result["spawned_revisions"][0]
    assert new_rev["revision_number"] == 2

    # old baseline unchanged
    resolved = svc.resolve_baseline(db, baseline.id)
    assert [b.artifact_revision_id for b in resolved.bindings] == before
    assert db.get(m.ArtifactRevision, dr_rev.id).snapshot != db.get(m.ArtifactRevision, new_rev["revision_id"]).snapshot

    # new revision can be reviewed → confirmed → new baseline
    svc.submit_for_review(db, new_rev["revision_id"])
    svc.confirm_revision(db, new_rev["revision_id"], actor="alice")
    new_baseline = svc.create_baseline(db, project_id=project.id, name="1.1", artifact_revision_ids=[ur_rev.id, new_rev["revision_id"]])
    assert {b.artifact_revision_id for b in new_baseline.bindings} == {ur_rev.id, new_rev["revision_id"]}


# ---------------------------------------------------------------------------
# P1 Search
# ---------------------------------------------------------------------------


def test_search_favours_semantic_objects(db, project, requirement):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_s")
    tbl = svc.create_table(db, schema_id=schema.id, name="customers")
    svc.create_field(db, table_id=tbl.id, name="customer_id", data_type="UUID")
    results = svc.search_semantic(db, project.id, "customer_id")
    assert any(r["kind"] == "semantic_object" and r["semantic_id"] == "fld_customers_customer_id" for r in results)
    results2 = svc.search_semantic(db, project.id, "approval")
    assert any(r["kind"] == "semantic_object" and r["semantic_id"] == requirement.code for r in results2)
