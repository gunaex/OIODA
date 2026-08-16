#!/usr/bin/env python
"""P4 full-stack dogfood — Purchase Approval V1 -> V2 with ecosystem handoffs.

Runs the complete Document Again workspace loop (requirements, UR/DR, DB, flow,
API, architecture, decision) through confirmation -> baseline, PM/QA handoffs
(durable outbox), impact analysis V2, OpenAPI import/export, export V2/V3, and
the historical-truth check that a later 3-level change never alters the frozen
2-level baseline.

Run against a fresh, migrated database (DA_DB_PATH / data/document-again.db).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def main() -> int:
    with TestClient(app) as c:
        H = {"X-Actor": "kanphong", "X-Account-Id": "acc-kanphong", "X-Actor-Name": "Kanphong", "X-Tenant-Id": "t-main"}

        # ── V1: 2-level approval ──
        p = c.post("/api/projects", json={"key": "PURCH4", "name": "Purchase Approval"}, headers=H).json()
        pid = p["id"]
        check("V1 create project", bool(pid))

        req = c.post("/api/requirements", json={"project_id": pid, "title": "2-level approval", "priority": "MUST"}, headers=H).json()
        check("V1 requirement", req["code"] == "REQ-0001")

        ur = c.post("/api/artifacts", json={"project_id": pid, "type": "UR", "title": "UR v1"}, headers=H).json()
        ur_rev = ur["revisions"][0]
        c.post(f"/api/revisions/{ur_rev['id']}/submit-for-review")
        c.post(f"/api/revisions/{ur_rev['id']}/confirm", json={"comment": "ok"}, headers=H)
        check("V1 UR confirmed", c.get(f"/api/revisions/{ur_rev['id']}").json()["status"] == "CONFIRMED")

        schema = c.post("/api/db-schemas", json={"project_id": pid, "name": "core", "semantic_id": "sch_core"}).json()
        tbl = c.post("/api/db-tables", json={"schema_id": schema["id"], "name": "approval"}).json()
        c.post("/api/db-fields", json={"table_id": tbl["id"], "name": "id", "data_type": "UUID", "primary_key": True})
        ep = c.post("/api/api-endpoints", json={"project_id": pid, "method": "POST", "path": "/approvals"}, headers=H).json()
        flow = c.post("/api/flows", json={"project_id": pid, "name": "Approval Flow", "semantic_id": "flow_approval"}).json()
        c.post("/api/flow-steps", json={"flow_id": flow["id"], "name": "Submit", "semantic_id": "flow_step_submit", "step_type": "START"})
        c.post("/api/flow-steps", json={"flow_id": flow["id"], "name": "Manager", "semantic_id": "flow_step_manager", "step_type": "APPROVAL"})
        c.post("/api/flow-steps", json={"flow_id": flow["id"], "name": "Approved", "semantic_id": "flow_step_approved", "step_type": "END"})
        arch = c.post("/api/architecture-diagrams", json={"project_id": pid, "name": "Arch", "semantic_id": "arch_main"}, headers=H).json()
        c.post("/api/architecture-nodes", json={"diagram_id": arch["id"], "name": "API", "semantic_id": "svc_api", "node_type": "SERVICE"})
        dec = c.post("/api/decisions", json={"project_id": pid, "title": "2-level for now", "content": "scope"}, headers=H).json()
        check("V1 structured design", bool(ep.get("id")) and bool(dec.get("id")))

        dr = c.post("/api/artifacts", json={"project_id": pid, "type": "DR", "title": "DR v1"}, headers=H).json()
        dr_rev = dr["revisions"][0]
        c.post(f"/api/revisions/{dr_rev['id']}/submit-for-review")
        c.post(f"/api/revisions/{dr_rev['id']}/confirm", json={"comment": "DR v1"}, headers=H)
        check("V1 DR confirmed with snapshot", "flows" in c.get(f"/api/revisions/{dr_rev['id']}").json()["snapshot"]["technical_design"])

        baseline1 = c.post("/api/baselines", json={"project_id": pid, "name": "v1", "artifact_revision_ids": [ur_rev["id"], dr_rev["id"]]}, headers=H).json()
        check("V1 baseline", len(baseline1["bindings"]) == 2)

        # PM + QA handoffs -> durable outbox (delivery target = orchestrator)
        c.post("/api/handoffs/execution", json={"project_id": pid, "baseline_id": baseline1["id"]}, headers=H)
        c.post("/api/handoffs/qa", json={"project_id": pid, "baseline_id": baseline1["id"], "requirement_ids": ["REQ-0001"]}, headers=H)
        outbox = c.get("/api/outbox").json()
        check("V1 handoffs queued", sum(1 for o in outbox if o["status"] == "PENDING") >= 2)

        # external references
        c.post("/api/external-references", json={"project_id": pid, "semantic_id": "REQ-0001", "service": "pm-again", "external_id": "PM-V1", "relation_type": "IMPLEMENTED_BY"})
        check("V1 external reference", len(c.get(f"/api/projects/{pid}/external-references").json()) == 1)

        # ── V2: conditional 3-level approval (amount > 1,000,000 THB) ──
        c.post("/api/change-requests", json={"project_id": pid, "title": "Add level 3 for >1M THB", "description": "conditional"}, headers=H)
        c.post("/api/change-sets", json={"project_id": pid, "name": "3-level", "items": [{"semantic_id": "REQ-0001", "change_type": "MODIFIED"}]}, headers=H)
        impact = c.get(f"/api/projects/{pid}/impact-v2/REQ-0001").json()
        check("V2 impact analysis", "affected" in impact)

        new_ur = c.post(f"/api/artifacts/{ur['id']}/revisions", json={}, headers=H).json()
        c.post(f"/api/revisions/{new_ur['id']}/submit-for-review")
        c.post(f"/api/revisions/{new_ur['id']}/confirm", json={"comment": "UR v2"}, headers=H)
        c.post("/api/flow-steps", json={"flow_id": flow["id"], "name": "Director", "semantic_id": "flow_step_director", "step_type": "APPROVAL"})
        new_dr = c.post(f"/api/artifacts/{dr['id']}/revisions", json={}, headers=H).json()
        c.post(f"/api/revisions/{new_dr['id']}/submit-for-review")
        c.post(f"/api/revisions/{new_dr['id']}/confirm", json={"comment": "DR v2"}, headers=H)
        baseline2 = c.post("/api/baselines", json={"project_id": pid, "name": "v2", "artifact_revision_ids": [new_ur["id"], new_dr["id"]]}, headers=H).json()
        check("V2 baseline", len(baseline2["bindings"]) == 2)

        c.post("/api/handoffs/execution", json={"project_id": pid, "baseline_id": baseline2["id"]}, headers=H)
        c.post("/api/handoffs/qa", json={"project_id": pid, "baseline_id": baseline2["id"], "requirement_ids": ["REQ-0001"]}, headers=H)
        c.post("/api/external-references", json={"project_id": pid, "semantic_id": "REQ-0001", "service": "pm-again", "external_id": "PM-V2", "relation_type": "IMPLEMENTED_BY"})
        check("V2 external reference", len(c.get(f"/api/projects/{pid}/external-references").json()) == 2)

        # ── Historical truth ──
        old_b = c.get(f"/api/baselines/{baseline1['id']}").json()
        dr_bind = next(b for b in old_b["bindings"] if b["artifact_id"] == dr["id"])
        check("OLD baseline still binds DR rev1", dr_bind["artifact_revision_id"] == dr_rev["id"])
        v1_flow = c.get(f"/api/revisions/{dr_rev['id']}/export?format=json").json()["technical_design"]["flows"]["flow_approval"]["steps"]
        v2_flow = c.get(f"/api/revisions/{new_dr['id']}/export?format=json").json()["technical_design"]["flows"]["flow_approval"]["steps"]
        check("V1 flow has no director step", "flow_step_director" not in v1_flow)
        check("V2 flow has director step", "flow_step_director" in v2_flow)

        # Export both packages reproducibly
        pkg1 = c.get(f"/api/baselines/{baseline1['id']}/package-v2")
        pkg2 = c.get(f"/api/baselines/{baseline2['id']}/package-v2")
        check("V1+V2 package exports", pkg1.content[:2] == b"PK" and pkg2.content[:2] == b"PK")

        # OpenAPI export from historical revision
        oas1 = c.get(f"/api/revisions/{dr_rev['id']}/openapi").json()
        check("V1 OpenAPI reproducible", "/approvals" in oas1["paths"])

    print()
    failed = [r for r in results if not r[1]]
    print(f"P4 dogfood: {len(results) - len(failed)}/{len(results)} steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
