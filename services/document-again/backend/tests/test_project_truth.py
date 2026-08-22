from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DA_DB_PATH", tempfile.mkstemp(suffix=".db")[1])

from app import services as svc  # noqa: E402
from app.db import Base  # noqa: E402
from app.deliverables import human  # noqa: E402
from app.deliverables import service as deliverable_service  # noqa: E402
from app.project_truth import build_project_truth, normalize_bindings  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'truth.db'}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(conn, _): conn.execute("pragma foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    engine.dispose()


def project(meta=None):
    return SimpleNamespace(id="doc-1", project_meta={"workspace_bindings": meta or {}})


def bound_project():
    return project({"v1": {
        "pm": {"service": "PM_AGAIN", "external_project_id": "pm-1", "binding_status": "BOUND"},
        "qa": [{"service": "QA_AGAIN", "external_project_id": "qa-1", "scope_id": "scope-1", "binding_status": "BOUND"}],
        "infra": {"service": "INFRA_AGAIN", "external_project_id": "design-1", "binding_status": "BOUND"},
    }})


def healthy_handler(request: httpx.Request):
    path = request.url.path
    if path.endswith("/dashboard") and "/pm-1/" in path:
        return httpx.Response(200, json={"status": "IN_PROGRESS", "updated_at": datetime.now(timezone.utc).isoformat()})
    if path.endswith("/gantt"):
        return httpx.Response(200, json=[
            {"id": 1, "is_milestone": True, "start_date": "2026-08-01", "end_date": "2026-08-02", "dependencies": None},
            {"id": 2, "is_milestone": False, "start_date": None, "end_date": None, "dependencies": "1"},
        ])
    if path.endswith("/effort-estimates/summary"):
        return httpx.Response(200, json={"total_person_days": 12})
    if path.endswith("/dashboard") and "/qa-1/" in path:
        return httpx.Response(200, json={"total_cases": 10, "result_counts": {"PASSED": 5, "NOT_RUN": 5},
            "pass_rate": 50, "evidence_completeness": 40})
    if path.endswith("/suites"):
        return httpx.Response(200, json=[{"id": 1, "name": "Regression"}])
    if path.endswith("/defects"):
        return httpx.Response(200, json=[{"id": 9, "status": "OPEN", "severity": "P1"}])
    if path.endswith("/designs/design-1"):
        return httpx.Response(200, json={"design": {"designId": "design-1", "revision": 7,
            "flow": {"nodes": [{"nodeId": "n1"}], "edges": [{"source": "n1", "target": "n2"}]}}})
    if path.endswith("/environments"):
        return httpx.Response(200, json={"environments": [{"environmentId": "prod"}]})
    if path.endswith("/production-readiness"):
        return httpx.Response(200, json={"readinessRecords": [{"status": "PARTIAL"}]})
    return httpx.Response(404, json={"detail": path})


def factory(handler):
    transport = httpx.MockTransport(handler)
    return lambda **kwargs: httpx.Client(transport=transport, **kwargs)


def test_binding_contract_valid_and_legacy_migration():
    current = normalize_bindings(bound_project())
    assert current["contract_version"] == "project_bindings/v1"
    assert current["pm"]["external_project_id"] == "pm-1"
    legacy = normalize_bindings(project({"pm_project_slug": "legacy", "qa_project_slugs": {"h": "qa"}}))
    assert legacy["pm"]["source"] == "LEGACY_POINTER"
    assert legacy["qa"][0]["scope_id"] == "h"


def test_unbound_sources_are_not_empty_truth():
    snap = build_project_truth(project(), client_factory=factory(healthy_handler))
    assert snap["pm"] is None and snap["sources"]["pm"]["source_status"] == "UNBOUND"
    assert snap["qa"] is None and snap["sources"]["qa"]["source_status"] == "UNBOUND"
    assert snap["infra"] is None and snap["sources"]["infra"]["source_status"] == "UNBOUND"
    assert snap["downstream_call_count"] == 0


def test_all_sources_healthy_with_provenance():
    snap = build_project_truth(bound_project(), "Bearer test", factory(healthy_handler))
    assert snap["contract_version"] == "project_truth/v1"
    assert snap["pm"]["schedule_status"] == "AVAILABLE"
    assert snap["qa"]["readiness_status"] == "BLOCKED"
    assert snap["infra"]["architecture_revision"] == 7
    assert snap["qa"]["provenance"]["source_service"] == "QA_AGAIN"
    assert snap["downstream_call_count"] == 9


@pytest.mark.parametrize("code,expected", [(401, "UNAUTHORIZED"), (403, "FORBIDDEN"), (404, "INVALID"), (500, "ERROR")])
def test_auth_and_server_failures_are_distinct(code, expected):
    def handler(request): return httpx.Response(code, json={"detail": "owner failure"})
    snap = build_project_truth(bound_project(), client_factory=factory(handler))
    assert {snap["sources"][name]["source_status"] for name in ("pm", "qa", "infra")} == {expected}
    assert snap["pm"] is None and snap["qa"] is None and snap["infra"] is None


def test_old_source_timestamp_is_marked_stale():
    def handler(request):
        response = healthy_handler(request)
        if request.url.path.endswith("/dashboard") and "/pm-1/" in request.url.path:
            return httpx.Response(200, json={"status": "IN_PROGRESS", "updated_at": "2020-01-01T00:00:00Z"})
        return response
    snap = build_project_truth(bound_project(), client_factory=factory(handler))
    assert snap["sources"]["pm"]["freshness"] == "STALE"
    assert snap["sources"]["pm"]["source_status"] == "STALE"
    assert snap["overall_freshness"] == "STALE"


def test_one_source_unavailable_preserves_other_truth():
    def handler(request):
        if "/api/pm-1/" in request.url.path or "/api/pm-1" in request.url.path:
            raise httpx.ConnectError("pm down", request=request)
        return healthy_handler(request)
    snap = build_project_truth(bound_project(), client_factory=factory(handler))
    assert snap["sources"]["pm"]["source_status"] == "UNAVAILABLE"
    assert snap["pm"] is None
    assert snap["qa"]["test_count"] == 10
    assert snap["infra"]["architecture_status"] == "AVAILABLE"


def test_timeout_is_unavailable_not_zero():
    def handler(request): raise httpx.ReadTimeout("slow", request=request)
    snap = build_project_truth(bound_project(), client_factory=factory(handler))
    assert snap["sources"]["pm"]["source_status"] == "UNAVAILABLE"
    assert snap["pm"] is None
    assert "schedule_item_count" not in (snap["pm"] or {})


def test_combined_truth_drives_migration_precheck_with_reasons_and_provenance(db):
    p = svc.create_project(db, key="TRUTH", name="Truth Project", description="migration scope")
    deliverable_service.set_profile(db, p, {"primary_type": "CLOUD_MIGRATION", "current_phase": "DESIGN"})
    snap = build_project_truth(bound_project(), client_factory=factory(healthy_handler))
    # Deterministic mixed scenario: PM schedule partial, QA blocked, Infra ready.
    snap["pm"]["schedule_status"] = "PARTIAL"
    result = human.precheck(db, p, "HD-MIG-01", snap)
    external = [std for section in result["sections"] for std in section["standards"] if std["authority"] != "DOCUMENT_AGAIN"]
    assert result["readiness"] == "READY_WITH_GAPS"
    assert any(std["state"] == "PARTIAL" and std["authority"] == "PM_AGAIN" for std in external)
    assert all(std.get("provenance", {}).get("source_service") == std["authority"] for std in external)
    dependencies = {row["name"]: row for row in result["cross_service_dependencies"]}
    assert dependencies["Migration Schedule"]["state"] == "PARTIAL"
    assert dependencies["QA Readiness"]["state"] == "BLOCKED"
    assert "1 high/critical" in dependencies["QA Readiness"]["reason"]
    assert dependencies["Target Architecture"]["state"] == "READY"
    assert dependencies["Target Architecture"]["provenance"]["source_revision"] == "7"


def test_unavailable_pm_precheck_is_unknown_not_missing(db):
    p = svc.create_project(db, key="DOWN", name="Down Project", description="scope")
    deliverable_service.set_profile(db, p, {"primary_type": "CLOUD_MIGRATION", "current_phase": "DESIGN"})
    snap = build_project_truth(bound_project(), client_factory=factory(lambda request: httpx.Response(500, json={})))
    result = human.precheck(db, p, "HD-MIG-01", snap)
    pm_rows = [std for section in result["sections"] for std in section["standards"] if std["authority"] == "PM_AGAIN"]
    assert pm_rows and all(row["state"] == "UNKNOWN" for row in pm_rows)
    assert result["unknown_modules"] == len(pm_rows)
    assert all("could not be verified" in row["reason"] for row in pm_rows)
