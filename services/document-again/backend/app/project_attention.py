"""Deterministic, read-only attention projection over project_truth/v1."""
from __future__ import annotations

from typing import Any

RANK = {"BLOCKER": 0, "ISSUE": 1, "UNVERIFIED": 2, "INFO": 3}


def build_project_attention(truth: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    def add(domain: str, priority: str, code: str, title: str, detail: str | None = None) -> None:
        items.append({"id": f"{domain.lower()}-{code.lower()}", "domain": domain, "priority": priority,
                      "code": code, "title": title, "detail": detail})

    for key, label in (("pm", "PM"), ("qa", "QA"), ("infra", "INFRA")):
        status = truth.get("sources", {}).get(key, {}).get("source_status", "UNKNOWN")
        if status not in {"OK", "EMPTY"}:
            add(label, "UNVERIFIED", f"SOURCE_{status}", f"{label} attention is {status.lower()}.")

    pm = truth.get("pm")
    if pm:
        attn = pm.get("attention") or {}
        if attn.get("blocked_dependency_count"):
            add("PM", "BLOCKER", "BLOCKED_DEPENDENCIES",
                f"{attn['blocked_dependency_count']} blocked dependency link(s).")
        if attn.get("slipping_item_count"):
            add("PM", "ISSUE", "SLIPPING_DELIVERY", f"{attn['slipping_item_count']} scheduled item(s) overdue.")
        variance = attn.get("effort_variance") or {}
        if variance.get("status") in {"over_budget", "critical", "warning"}:
            add("PM", "ISSUE", "EFFORT_VARIANCE", f"Effort budget status is {variance['status'].replace('_', ' ')}.")

    qa = truth.get("qa")
    if qa:
        failed = (qa.get("failed_test_count") or 0) + (qa.get("blocked_test_count") or 0)
        if failed:
            add("QA", "BLOCKER", "FAILED_TESTS", f"{failed} failed or blocked test(s).")
        if qa.get("blocking_defect_count"):
            add("QA", "BLOCKER", "BLOCKING_DEFECTS", f"{qa['blocking_defect_count']} blocking defect(s).")
        if qa.get("remaining_test_count"):
            add("QA", "ISSUE", "REMAINING_TESTS", f"{qa['remaining_test_count']} test(s) not run.")
        if qa.get("evidence_status") in {"MISSING", "PARTIAL"}:
            add("QA", "ISSUE", "EVIDENCE_GAP", f"QA evidence is {qa['evidence_status'].lower()}.")

    infra = truth.get("infra")
    if infra:
        if infra.get("feasibility_exception_count"):
            add("INFRA", "BLOCKER", "FEASIBILITY", f"{infra['feasibility_exception_count']} feasibility exception(s).")
        if infra.get("connectivity_exception_count"):
            add("INFRA", "BLOCKER", "CONNECTIVITY", f"{infra['connectivity_exception_count']} connectivity exception(s).")
        for field, code, title in (
            ("environment_readiness_status", "ENVIRONMENT_READINESS", "Environment readiness is unverified."),
            ("implementation_readiness_status", "IMPLEMENTATION_READINESS", "Implementation readiness is unverified."),
            ("preflight_status", "PREFLIGHT", "Preflight readiness is unverified."),
            ("readiness_status", "PRODUCTION_READINESS", "Production readiness is unverified."),
        ):
            value = infra.get(field)
            if value in {"BLOCKED", "NOT_READY", "FAILED"}:
                add("INFRA", "BLOCKER", code, title.replace("unverified", value.lower()))
            elif value in {"UNKNOWN", None}:
                add("INFRA", "UNVERIFIED", code, title)

    items.sort(key=lambda row: (RANK[row["priority"]], row["domain"], row["code"]))
    counts = {name.lower(): sum(1 for row in items if row["priority"] == name)
              for name in ("BLOCKER", "ISSUE", "UNVERIFIED")}
    return {"contract_version": "project_attention/v1", "counts": counts, "items": items,
            "domains": {key: {"source_status": truth.get("sources", {}).get(key, {}).get("source_status", "UNKNOWN")}
                        for key in ("pm", "qa", "infra")}}
