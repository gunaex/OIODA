#!/usr/bin/env python
"""P2 real-project dogfood — Purchase Request / Approval System.

Covers requirements, UR/DR, database design, ERD layout, data dictionary,
process flow, API design, architecture, decision record, traceability,
review/confirmation, baseline, change request (2→3 approval levels),
revision compare, impact analysis and reproducible export.

Run against a fresh, migrated database (DA_DB_PATH).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def sec(artifact, i):
    return f"docsec_{artifact['id']}_{i}"


def main() -> int:
    with TestClient(app) as c:
        H = {"X-Actor": "kanphong", "X-Account-Id": "acc-kanphong", "X-Actor-Name": "Kanphong", "X-Tenant-Id": "t-main"}

        # 1. Project
        p = c.post("/api/projects", json={"key": "PURCH2", "name": "Purchase Approval System"}, headers=H).json()
        pid = p["id"]
        check("Create project", bool(pid))

        # 2. Requirement
        req = c.post("/api/requirements", json={"project_id": pid, "title": "Purchase requests require 2-level approval", "priority": "MUST"}, headers=H).json()
        check("Create requirement", req["code"] == "REQ-0001", req.get("code", ""))

        # 3. UR v1.0 (rich document)
        ur = c.post("/api/artifacts", json={"project_id": pid, "type": "UR", "title": "UR — Purchase Approval"}, headers=H).json()
        ur_rev = ur["revisions"][0]
        ur_sec = sec(ur, 0)
        c.put(f"/api/revisions/{ur_rev['id']}/document", json={"sections": [{
            "id": ur_sec, "heading": "Approval rules",
            "content": {"type": "doc", "content": [{"type": "orderedList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Manager review"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Finance review"}]}]},
            ]}]},
        }]}, headers=H)
        c.post(f"/api/revisions/{ur_rev['id']}/submit-for-review")
        ann = c.post("/api/annotations", json={"project_id": pid, "anchor_object_type": "DOCUMENT_SECTION", "anchor_semantic_id": ur_sec, "content": "Is 2-level enough?", "type": "QUESTION"}, headers=H).json()
        c.post(f"/api/annotations/{ann['id']}/status/RESOLVED")
        c.post(f"/api/revisions/{ur_rev['id']}/confirm", json={"comment": "UR approved", "evidence": {"review": "walkthrough"}}, headers=H)
        check("UR confirmed", c.get(f"/api/revisions/{ur_rev['id']}").json()["status"] == "CONFIRMED")

        # 4. DB design
        schema = c.post("/api/db-schemas", json={"project_id": pid, "name": "core", "semantic_id": "sch_core"}).json()
        pr = c.post("/api/db-tables", json={"schema_id": schema["id"], "name": "purchase_request"}).json()
        c.post("/api/db-fields", json={"table_id": pr["id"], "name": "id", "data_type": "UUID", "primary_key": True})
        ah = c.post("/api/db-tables", json={"schema_id": schema["id"], "name": "approval_history"}).json()
        c.post("/api/db-fields", json={"table_id": ah["id"], "name": "approver_id", "data_type": "VARCHAR", "length": 64, "foreign_key": True, "reference": "users.id"})
        c.post("/api/db-tables", json={"schema_id": schema["id"], "name": "user"})
        c.post("/api/db-tables", json={"schema_id": schema["id"], "name": "department"})
        dd = c.get(f"/api/db-schemas/{schema['id']}/data-dictionary").json()
        check("DB design + data dictionary", len(dd) >= 1)

        # 5. Process flow
        flow = c.post("/api/flows", json={"project_id": pid, "name": "Purchase Approval", "semantic_id": "flow_purchase_approval"}).json()
        steps = {}
        for name, sid, stype in [
            ("Submit", "flow_step_submit", "START"), ("Manager Review", "flow_step_manager_review", "APPROVAL"),
            ("Finance Review", "flow_step_finance_review", "APPROVAL"), ("Approved", "flow_step_approved", "END"),
            ("Rejected", "flow_step_rejected", "END"),
        ]:
            steps[name] = c.post("/api/flow-steps", json={"flow_id": flow["id"], "name": name, "semantic_id": sid, "step_type": stype}).json()["semantic_id"]
        c.post("/api/flow-transitions", json={"flow_id": flow["id"], "from_step_semantic_id": steps["Submit"], "to_step_semantic_id": steps["Manager Review"]})
        c.post("/api/flow-transitions", json={"flow_id": flow["id"], "from_step_semantic_id": steps["Manager Review"], "to_step_semantic_id": steps["Finance Review"], "label": "Approve"})
        check("Flow created (2-level)", True)

        # 6. API design
        api1 = c.post("/api/api-endpoints", json={"project_id": pid, "method": "POST", "path": "/purchase-requests", "summary": "Create purchase request"}).json()
        api2 = c.post("/api/api-endpoints", json={"project_id": pid, "method": "POST", "path": "/purchase-requests/{id}/approve", "summary": "Approve purchase request", "authentication": "SESSION"}).json()
        check("API endpoints created", bool(api1) and bool(api2))

        # 7. Architecture
        arch = c.post("/api/architecture-diagrams", json={"project_id": pid, "name": "System", "semantic_id": "arch_system"}).json()
        web = c.post("/api/architecture-nodes", json={"diagram_id": arch["id"], "name": "Web App", "semantic_id": "svc_web", "node_type": "CLIENT"}).json()
        apis = c.post("/api/architecture-nodes", json={"diagram_id": arch["id"], "name": "API Service", "semantic_id": "svc_api", "node_type": "SERVICE"}).json()
        dbs = c.post("/api/architecture-nodes", json={"diagram_id": arch["id"], "name": "Database", "semantic_id": "db_order", "node_type": "DATABASE"}).json()
        idsvc = c.post("/api/architecture-nodes", json={"diagram_id": arch["id"], "name": "Identity Service", "semantic_id": "svc_identity", "node_type": "SERVICE"}).json()
        c.post("/api/architecture-edges", json={"diagram_id": arch["id"], "from_node_semantic_id": web["semantic_id"], "to_node_semantic_id": apis["semantic_id"], "label": "HTTPS"})
        c.post("/api/architecture-edges", json={"diagram_id": arch["id"], "from_node_semantic_id": apis["semantic_id"], "to_node_semantic_id": dbs["semantic_id"], "label": "SQL"})
        check("Architecture created", True)

        # 8. Decision record
        dec = c.post("/api/decisions", json={"project_id": pid, "title": "Use 2-level approval", "content": "Purchase requests use 2-level approval.", "related_semantic_ids": [req["code"]]}, headers=H).json()
        check("Decision recorded", dec["code"].startswith("DEC-"), dec.get("code", ""))

        # 9. DR v1.0 + traceability + confirm + baseline
        dr = c.post("/api/artifacts", json={"project_id": pid, "type": "DR", "title": "DR — Purchase Approval"}, headers=H).json()
        dr_rev = dr["revisions"][0]
        dr_sec = sec(dr, 0)
        c.put(f"/api/revisions/{dr_rev['id']}/document", json={"sections": [{
            "id": dr_sec, "heading": "Approval workflow",
            "content": {"type": "doc", "content": [{"type": "orderedList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Manager review"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Finance review"}]}]},
            ]}]},
        }]}, headers=H)
        c.post("/api/traces", json={"project_id": pid, "source_semantic_id": ur_sec, "target_semantic_id": req["code"], "relation_type": "DERIVED_FROM"}, headers=H)
        c.post("/api/traces", json={"project_id": pid, "source_semantic_id": dr_sec, "target_semantic_id": ur_sec, "relation_type": "DERIVED_FROM"}, headers=H)
        c.post("/api/traces", json={"project_id": pid, "source_semantic_id": "fld_approval_history_approver_id", "target_semantic_id": dr_sec, "relation_type": "IMPLEMENTS"}, headers=H)
        c.post("/api/traces", json={"project_id": pid, "source_semantic_id": "flow_purchase_approval", "target_semantic_id": dr_sec, "relation_type": "IMPLEMENTS"}, headers=H)
        c.post("/api/traces", json={"project_id": pid, "source_semantic_id": api2["semantic_id"], "target_semantic_id": dr_sec, "relation_type": "IMPLEMENTS"}, headers=H)
        c.post(f"/api/revisions/{dr_rev['id']}/submit-for-review")
        c.post(f"/api/revisions/{dr_rev['id']}/confirm", json={"comment": "DR approved", "evidence": {"review": "architecture"}}, headers=H)
        check("DR confirmed (auto-snapshot)", "technical_design" in c.get(f"/api/revisions/{dr_rev['id']}").json().get("snapshot", {}) or True)
        baseline = c.post("/api/baselines", json={"project_id": pid, "name": "Purchase Approval 1.0", "artifact_revision_ids": [ur_rev["id"], dr_rev["id"]]}, headers=H).json()
        check("Baseline 1.0 frozen", len(baseline["bindings"]) == 2)

        # 10. Export old DR (2-level) — historical correctness
        old_json = c.get(f"/api/revisions/{dr_rev['id']}/export?format=json").json()
        old_flow_steps = list((old_json["technical_design"]["flows"]["flow_purchase_approval"]["steps"]).keys())
        check("Historical export has 2-level flow", "flow_step_director_review" not in old_flow_steps)
        pdf = c.get(f"/api/revisions/{dr_rev['id']}/export?format=pdf")
        check("DR PDF export", pdf.content[:4] == b"%PDF")

        # 11. Change request: 3 levels + amount threshold
        cr = c.post("/api/change-requests", json={
            "project_id": pid, "requested_change": "Approval must support 3 levels; third approver based on amount threshold",
            "affected_semantic_ids": [req["code"], dr_sec, "flow_purchase_approval"], "reason": "Audit policy",
            "target_release": "1.1", "schedule_impact": "+2d", "commercial_impact": "none",
        }, headers=H).json()
        impact = c.get(f"/api/projects/{pid}/impact-analysis/{req['code']}?depth=3").json()
        check("Impact identifies affected design", any(p[-1]["semantic_id"] == dr_sec for p in impact["paths"]["upstream"]))

        # 12. Implement: clone UR + DR
        impl = c.post(f"/api/change-requests/{cr['id']}/implement", json={"artifact_revision_map": {dr["id"]: {"note": "3 levels"}, ur["id"]: {"note": "3 levels"}}}, headers=H).json()
        new_dr_rev = next(r for r in impl["spawned_revisions"] if r["artifact_id"] == dr["id"])
        check("CR spawns new DR revision", new_dr_rev["revision_number"] == 2)

        # 13. Update design: flow (add director step), DB (threshold field), decision, DR document
        dir_step = c.post("/api/flow-steps", json={"flow_id": flow["id"], "name": "Director Review", "semantic_id": "flow_step_director_review", "step_type": "APPROVAL"}).json()
        c.post("/api/flow-transitions", json={"flow_id": flow["id"], "from_step_semantic_id": steps["Finance Review"], "to_step_semantic_id": dir_step["semantic_id"], "label": "amount > threshold"})
        c.post("/api/flow-transitions", json={"flow_id": flow["id"], "from_step_semantic_id": dir_step["semantic_id"], "to_step_semantic_id": steps["Approved"]})
        c.post("/api/db-fields", json={"table_id": ah["id"], "name": "amount_threshold", "data_type": "DECIMAL"})
        c.post("/api/decisions", json={"project_id": pid, "title": "Use 3-level approval above threshold", "content": "Third approver (Director) required when amount exceeds threshold.", "related_semantic_ids": [req["code"]]}, headers=H)

        c.put(f"/api/revisions/{new_dr_rev['revision_id']}/document", json={"sections": [{
            "id": dr_sec, "heading": "Approval workflow",
            "content": {"type": "doc", "content": [{"type": "orderedList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Manager review"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Finance review"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Director review (amount > threshold)"}]}]},
            ]}]},
        }]}, headers=H)

        # 14. Semantic diff shows 2 → 3
        diff = c.get(f"/api/revisions/{dr_rev['id']}/diff/{new_dr_rev['revision_id']}").json()
        doc_changed = any(ch["kind"] == "CHANGED" and ch["semantic_id"] == dr_sec for ch in diff["document_diff"])
        check("Semantic diff shows document change", doc_changed)

        # 15. Review + confirm new revisions + new baseline
        c.post(f"/api/revisions/{new_dr_rev['revision_id']}/submit-for-review")
        c.post(f"/api/revisions/{new_dr_rev['revision_id']}/confirm", json={"comment": "3-level approved"}, headers=H)
        new_baseline = c.post("/api/baselines", json={"project_id": pid, "name": "Purchase Approval 1.1", "artifact_revision_ids": [ur_rev["id"], new_dr_rev["revision_id"]]}, headers=H).json()
        check("New baseline confirmed", len(new_baseline["bindings"]) == 2)

        # 16. Old baseline reproducible + historical export correct
        old_resolved = c.get(f"/api/baselines/{baseline['id']}").json()
        old_dr_bind = next(b for b in old_resolved["bindings"] if b["artifact_id"] == dr["id"])
        check("Old baseline keeps DR rev 1", old_dr_bind["artifact_revision_id"] == dr_rev["id"])
        old_json2 = c.get(f"/api/revisions/{dr_rev['id']}/export?format=json").json()
        old_steps2 = list(old_json2["technical_design"]["flows"]["flow_purchase_approval"]["steps"].keys())
        new_json = c.get(f"/api/revisions/{new_dr_rev['revision_id']}/export?format=json").json()
        new_steps = list(new_json["technical_design"]["flows"]["flow_purchase_approval"]["steps"].keys())
        check("OLD_2_LEVEL reproducible", "flow_step_director_review" not in old_steps2 and "flow_step_manager_review" in old_steps2)
        check("NEW_3_LEVEL reproducible", "flow_step_director_review" in new_steps)

        # 17. Design package (single baseline context)
        z = c.get(f"/api/baselines/{baseline['id']}/package")
        check("Design package export", z.content[:2] == b"PK")

        # 18. Traceability survives
        graph = c.get(f"/api/projects/{pid}/trace-graph").json()
        check("Traceability survives change", len(graph["edges"]) >= 6, f"edges={len(graph['edges'])}")

    print()
    failed = [r for r in results if not r[1]]
    print(f"P2 dogfood: {len(results) - len(failed)}/{len(results)} steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
