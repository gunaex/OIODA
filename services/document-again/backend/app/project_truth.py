"""R17.1.2 derived, read-only cross-service project truth.

This module never persists bounded-service facts. It resolves explicit pointers
stored on the Document project, reads each owner in parallel, and returns a
versioned projection with provenance and honest degraded states.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

CONTRACT = "project_truth/v1"
SOURCE_TIMEOUT = float(os.environ.get("PROJECT_TRUTH_SOURCE_TIMEOUT_SECONDS", "5"))
FRESH_SECONDS = int(os.environ.get("PROJECT_TRUTH_FRESH_SECONDS", "300"))
STALE_SECONDS = int(os.environ.get("PROJECT_TRUTH_STALE_SECONDS", "1800"))
BASE_URLS = {
    "pm": os.environ.get("PM_AGAIN_URL", "http://oida-pm.internal:8000").rstrip("/"),
    "qa": os.environ.get("QA_AGAIN_URL", "http://oida-qa.internal:8000").rstrip("/"),
    "infra": os.environ.get("INFRA_AGAIN_URL", "http://oida-infra.internal:8080").rstrip("/"),
}
log = logging.getLogger("document-again.project-truth")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_bindings(project: Any) -> dict:
    """Return the v1 binding contract, migrating legacy pointers in memory."""
    raw = (project.project_meta or {}).get("workspace_bindings") or {}
    v1 = raw.get("v1") or {}

    pm = v1.get("pm")
    if not pm and raw.get("pm_project_slug"):
        pm = {"service": "PM_AGAIN", "external_project_id": raw["pm_project_slug"],
              "binding_status": "BOUND", "source": "LEGACY_POINTER"}

    qa = v1.get("qa") or []
    if not qa:
        qa = [
            {"service": "QA_AGAIN", "external_project_id": slug,
             "binding_status": "BOUND", "source": "LEGACY_POINTER", "scope_id": scope}
            for scope, slug in (raw.get("qa_project_slugs") or {}).items() if slug
        ]

    infra = v1.get("infra")
    if not infra and raw.get("infra_design_id"):
        infra = {"service": "INFRA_AGAIN", "external_project_id": raw["infra_design_id"],
                 "binding_status": "BOUND", "source": "LEGACY_POINTER"}

    return {
        "contract_version": "project_bindings/v1",
        "project_id": project.id,
        "document_project_id": project.id,
        "pm": pm or {"service": "PM_AGAIN", "external_project_id": None, "binding_status": "UNBOUND"},
        "qa": qa,
        "infra": infra or {"service": "INFRA_AGAIN", "external_project_id": None, "binding_status": "UNBOUND"},
    }


def _status_from_error(exc: Exception) -> tuple[str, str | None]:
    if isinstance(exc, httpx.TimeoutException):
        return "UNAVAILABLE", "TIMEOUT"
    if isinstance(exc, httpx.ConnectError):
        return "UNAVAILABLE", "CONNECT_ERROR"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return ({401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "INVALID"}.get(code, "ERROR"), f"HTTP_{code}")
    return "ERROR", exc.__class__.__name__.upper()


def _source(service: str, binding: Any, status: str, retrieved: datetime,
            *, revision: str | None = None, updated_at: str | None = None,
            error_code: str | None = None, error_message: str | None = None,
            duration_ms: float = 0) -> dict:
    freshness = "UNKNOWN"
    age = None
    if updated_at:
        try:
            stamp = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            age = max(0, int((retrieved - stamp).total_seconds()))
            freshness = "FRESH" if age <= FRESH_SECONDS else "AGING" if age <= STALE_SECONDS else "STALE"
        except (TypeError, ValueError):
            pass
    if freshness == "STALE" and status == "OK":
        status = "STALE"
    return {
        "source_service": service,
        "source_project_id": binding,
        "source_status": status,
        "source_revision_or_version": revision,
        "source_updated_at": updated_at,
        "retrieved_at": retrieved.isoformat(),
        "age_seconds": age,
        "freshness": freshness,
        "error_code": error_code,
        "error_message": error_message,
        "duration_ms": round(duration_ms, 1),
    }


def _get(client: httpx.Client, url: str) -> Any:
    response = client.get(url)
    response.raise_for_status()
    return response.json()


def _latest_timestamp(values: list[Any]) -> str | None:
    found: list[str] = []
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in {"updated_at", "updatedat", "changed_at", "changedat", "created_at", "createdat"} and isinstance(child, str):
                    found.append(child)
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(values)
    return max(found) if found else None


def _provenance(service: str, entity: str | None, revision: Any, retrieved: datetime) -> dict:
    return {"source_service": service, "source_entity_id": entity,
            "source_revision": str(revision) if revision is not None else None,
            "retrieved_at": retrieved.isoformat()}


def _read_pm(binding: dict, authorization: str | None, client_factory: Callable[..., httpx.Client]) -> dict:
    slug = binding.get("external_project_id")
    retrieved = _now()
    if not slug:
        return {"source": _source("PM_AGAIN", None, "UNBOUND", retrieved), "truth": None}
    started = time.monotonic()
    try:
        with client_factory(timeout=SOURCE_TIMEOUT, headers={"Authorization": authorization} if authorization else {}) as client:
            dashboard = _get(client, f"{BASE_URLS['pm']}/api/{slug}/dashboard")
            gantt = _get(client, f"{BASE_URLS['pm']}/api/{slug}/gantt")
            effort = _get(client, f"{BASE_URLS['pm']}/api/{slug}/effort-estimates/summary")
        milestones = [row for row in gantt if row.get("is_milestone") is True]
        scheduled = [row for row in gantt if row.get("start_date") or row.get("end_date")]
        dependencies = [row.get("dependencies") for row in gantt if row.get("dependencies")]
        updated = _latest_timestamp([dashboard, gantt, effort])
        revision = dashboard.get("revision") or dashboard.get("version")
        truth = {
            "project_status": dashboard.get("project", {}).get("status") or dashboard.get("status") or dashboard.get("rag"),
            "schedule_status": "AVAILABLE" if scheduled else "EMPTY",
            "schedule_item_count": len(gantt), "scheduled_item_count": len(scheduled),
            "milestone_status": "AVAILABLE" if milestones else "EMPTY", "milestone_count": len(milestones),
            "progress": dashboard.get("progress") or dashboard.get("summary") or dashboard.get("phase_completion"),
            "effort_status": "AVAILABLE" if effort else "EMPTY", "effort": effort,
            "dependency_status": "AVAILABLE" if dependencies else "EMPTY", "dependency_count": len(dependencies),
            "provenance": _provenance("PM_AGAIN", slug, revision, retrieved),
        }
        status = "EMPTY" if not gantt and not effort else "OK"
        return {"source": _source("PM_AGAIN", slug, status, retrieved, revision=str(revision) if revision else None,
                                   updated_at=updated, duration_ms=(time.monotonic()-started)*1000), "truth": truth}
    except Exception as exc:  # isolated source failure
        status, code = _status_from_error(exc)
        log.warning("project_truth_source", extra={"service": "PM_AGAIN", "binding": slug,
                    "result_status": status, "duration_ms": round((time.monotonic()-started)*1000, 1), "error_category": code})
        return {"source": _source("PM_AGAIN", slug, status, retrieved, error_code=code,
                                   error_message=str(exc), duration_ms=(time.monotonic()-started)*1000), "truth": None}


def _read_qa(bindings: list[dict], authorization: str | None, client_factory: Callable[..., httpx.Client]) -> dict:
    ids = [b.get("external_project_id") for b in bindings if b.get("external_project_id")]
    retrieved = _now()
    if not ids:
        return {"source": _source("QA_AGAIN", None, "UNBOUND", retrieved), "truth": None}
    started = time.monotonic()
    try:
        dashboards, suites, defects = [], [], []
        with client_factory(timeout=SOURCE_TIMEOUT, headers={"Authorization": authorization} if authorization else {}) as client:
            for slug in ids:
                dashboards.append(_get(client, f"{BASE_URLS['qa']}/api/{slug}/dashboard"))
                suites.extend(_get(client, f"{BASE_URLS['qa']}/api/{slug}/suites"))
                defects.extend(_get(client, f"{BASE_URLS['qa']}/api/{slug}/defects"))
        totals = [d.get("total_cases", 0) or 0 for d in dashboards]
        counts: dict[str, int] = {}
        for d in dashboards:
            for key, value in (d.get("result_counts") or {}).items(): counts[key] = counts.get(key, 0) + value
        open_defects = [d for d in defects if str(d.get("status", "OPEN")).upper() not in {"CLOSED", "RESOLVED", "REJECTED"}]
        # QA Again's actual severity contract is P0/P1/P2/P3/UNSPECIFIED.
        blocking = [d for d in open_defects if str(d.get("severity", "")).upper() in {"P0", "P1"}]
        evidence_values = [d.get("evidence_completeness") for d in dashboards if d.get("evidence_completeness") is not None]
        execution_count = sum(v for k, v in counts.items() if k.upper() != "NOT_RUN")
        truth = {
            "readiness_status": "BLOCKED" if blocking else "READY" if sum(totals) and execution_count else "NOT_STARTED",
            "test_definition_status": "AVAILABLE" if suites else "EMPTY", "suite_count": len(suites),
            "test_count": sum(totals), "execution_status": "STARTED" if execution_count else "NOT_STARTED",
            "result_counts": counts, "pass_rate": next((d.get("pass_rate") for d in reversed(dashboards) if d.get("pass_rate") is not None), None),
            "open_defect_count": len(open_defects), "blocking_defect_count": len(blocking),
            "evidence_status": "AVAILABLE" if any(evidence_values) else "EMPTY",
            "evidence_completeness": max(evidence_values) if evidence_values else None,
            "provenance": _provenance("QA_AGAIN", ",".join(ids), None, retrieved),
        }
        status = "EMPTY" if not suites and not dashboards else "OK"
        return {"source": _source("QA_AGAIN", ids, status, retrieved, updated_at=_latest_timestamp([dashboards, suites, defects]),
                                   duration_ms=(time.monotonic()-started)*1000), "truth": truth}
    except Exception as exc:
        status, code = _status_from_error(exc)
        log.warning("project_truth_source", extra={"service": "QA_AGAIN", "binding": ids,
                    "result_status": status, "duration_ms": round((time.monotonic()-started)*1000, 1), "error_category": code})
        return {"source": _source("QA_AGAIN", ids, status, retrieved, error_code=code,
                                   error_message=str(exc), duration_ms=(time.monotonic()-started)*1000), "truth": None}


def _read_infra(binding: dict, authorization: str | None, client_factory: Callable[..., httpx.Client]) -> dict:
    design_id = binding.get("external_project_id")
    retrieved = _now()
    if not design_id:
        return {"source": _source("INFRA_AGAIN", None, "UNBOUND", retrieved), "truth": None}
    started = time.monotonic()
    try:
        with client_factory(timeout=SOURCE_TIMEOUT, headers={"Authorization": authorization} if authorization else {}) as client:
            envelope = _get(client, f"{BASE_URLS['infra']}/api/v1/designs/{design_id}")
            environments = _get(client, f"{BASE_URLS['infra']}/api/v1/environments")
            readiness = _get(client, f"{BASE_URLS['infra']}/api/v1/production-readiness")
        design = envelope.get("design", envelope)
        flow = design.get("flow") or {}
        nodes, edges = flow.get("nodes") or [], flow.get("edges") or []
        envs = environments.get("environments", environments if isinstance(environments, list) else [])
        readiness_rows = readiness.get("readinessRecords", readiness.get("readiness", readiness.get("evaluations", readiness if isinstance(readiness, list) else [])))
        revision = design.get("revision") or design.get("version")
        truth = {
            "architecture_status": "AVAILABLE" if nodes else "PARTIAL" if design else "EMPTY",
            "architecture_revision": revision, "component_count": len(nodes),
            "connectivity_status": "AVAILABLE" if edges else "EMPTY", "connection_count": len(edges),
            "environment_status": "AVAILABLE" if envs else "EMPTY", "environment_count": len(envs),
            "readiness_status": (readiness_rows[0].get("status") if isinstance(readiness_rows, list) and readiness_rows else "UNKNOWN"),
            "provenance": _provenance("INFRA_AGAIN", design_id, revision, retrieved),
        }
        return {"source": _source("INFRA_AGAIN", design_id, "OK", retrieved, revision=str(revision) if revision is not None else None,
                                   updated_at=_latest_timestamp([design, envs, readiness_rows]), duration_ms=(time.monotonic()-started)*1000), "truth": truth}
    except Exception as exc:
        status, code = _status_from_error(exc)
        log.warning("project_truth_source", extra={"service": "INFRA_AGAIN", "binding": design_id,
                    "result_status": status, "duration_ms": round((time.monotonic()-started)*1000, 1), "error_category": code})
        return {"source": _source("INFRA_AGAIN", design_id, status, retrieved, error_code=code,
                                   error_message=str(exc), duration_ms=(time.monotonic()-started)*1000), "truth": None}


def build_project_truth(project: Any, authorization: str | None = None,
                        client_factory: Callable[..., httpx.Client] = httpx.Client) -> dict:
    started = time.monotonic()
    bindings = normalize_bindings(project)
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="project-truth") as pool:
        futures = {
            "pm": pool.submit(_read_pm, bindings["pm"], authorization, client_factory),
            "qa": pool.submit(_read_qa, bindings["qa"], authorization, client_factory),
            "infra": pool.submit(_read_infra, bindings["infra"], authorization, client_factory),
        }
        result = {name: future.result() for name, future in futures.items()}
    # Validation is observational and never rewrites bindings implicitly.
    bindings["pm"]["validation_status"] = result["pm"]["source"]["source_status"]
    for binding in bindings["qa"]:
        binding["validation_status"] = result["qa"]["source"]["source_status"]
    bindings["infra"]["validation_status"] = result["infra"]["source"]["source_status"]
    statuses = [result[name]["source"]["source_status"] for name in ("pm", "qa", "infra")]
    freshnesses = [result[name]["source"]["freshness"] for name in ("pm", "qa", "infra")]
    warnings = [f"{name.upper()} source is {result[name]['source']['source_status']}" for name in result
                if result[name]["source"]["source_status"] not in {"OK", "EMPTY"}]
    overall = "STALE" if "STALE" in freshnesses else "AGING" if "AGING" in freshnesses else "FRESH" if "FRESH" in freshnesses else "UNKNOWN"
    snapshot = {
        "contract_version": CONTRACT, "project_id": project.id, "generated_at": _now().isoformat(),
        "bindings": bindings, "sources": {k: v["source"] for k, v in result.items()},
        "pm": result["pm"]["truth"], "qa": result["qa"]["truth"], "infra": result["infra"]["truth"],
        "overall_freshness": overall, "partial": any(s not in {"OK", "EMPTY"} for s in statuses),
        "warnings": warnings, "duration_ms": round((time.monotonic()-started)*1000, 1),
        "downstream_call_count": (3 if bindings["pm"].get("external_project_id") else 0)
                                 + 3 * len([b for b in bindings["qa"] if b.get("external_project_id")])
                                 + (3 if bindings["infra"].get("external_project_id") else 0),
    }
    log.info("project_truth_complete", extra={"project_id": project.id, "request_result_status": statuses,
             "duration_ms": snapshot["duration_ms"], "downstream_call_count": snapshot["downstream_call_count"]})
    return snapshot
