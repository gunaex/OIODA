#!/usr/bin/env python
"""P1 integrated dogfood scenario.

Create Project → Requirement → UR (review/comment/resolve/confirm) → DR
→ DB design → data dictionary → trace links → baseline → change request
"3 approval levels" → impact → clone revision → modify design → semantic
diff → old baseline reproducible → review → new baseline → traceability.
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


def main() -> int:
    with TestClient(app) as c:
        # 1. Project
        p = c.post("/api/projects", json={"key": "PURCH", "name": "Purchase Approval"}, headers={"X-Actor": "kanphong"}).json()
        pid = p["id"]
        check("Create project", bool(pid))

        # 2. Requirement
        req = c.post("/api/requirements", json={"project_id": pid, "title": "Purchase request requires 2-level approval", "priority": "MUST"}, headers={"X-Actor": "kanphong"}).json()
        check("Create requirement", req["code"] == "REQ-0001", req.get("code", ""))

        # 3. UR v1.0 — rich document
        ur = c.post("/api/artifacts", json={"project_id": pid, "type": "UR", "title": "UR — Purchase Approval"}, headers={"X-Actor": "kanphong"}).json()
        ur_rev = ur["revisions"][0]
        ur_sections = [{
            "id": f"docsec_{ur['id']}_0", "heading": "Approval rules",
            "blocks": [{"kind": "numbered_list", "items": ["Manager review", "Finance review"]}],
        }]
        c.put(f"/api/revisions/{ur_rev['id']}/document", json={"sections": ur_sections}, headers={"X-Actor": "kanphong"})
        check("UR document saved (sections)", True)

        # 4. review + comment + resolve + confirm
        c.post(f"/api/revisions/{ur_rev['id']}/submit-for-review")
        ann = c.post("/api/annotations", json={"project_id": pid, "anchor_object_type": "DOCUMENT_SECTION", "anchor_semantic_id": ur_sections[0]["id"], "content": "Is 2-level enough?", "type": "QUESTION"}, headers={"X-Actor": "reviewer-a"}).json()
        check("Semantic comment anchor", ann["anchor_semantic_id"] == ur_sections[0]["id"])
        c.post(f"/api/annotations/{ann['id']}/status/RESOLVED")
        c.post(f"/api/revisions/{ur_rev['id']}/confirm", json={"comment": "UR approved", "evidence": {"review": "walkthrough"}}, headers={"X-Actor": "kanphong"})
        check("Confirm UR v1.0", c.get(f"/api/revisions/{ur_rev['id']}").json()["status"] == "CONFIRMED")

        # 5. DR v1.0
        dr = c.post("/api/artifacts", json={"project_id": pid, "type": "DR", "title": "DR — Purchase Approval"}, headers={"X-Actor": "kanphong"}).json()
        dr_rev = dr["revisions"][0]
        dr_sections = [{
            "id": f"docsec_{dr['id']}_0", "heading": "Approval workflow",
            "blocks": [{"kind": "numbered_list", "items": ["Manager review", "Finance review"]}],
        }]
        c.put(f"/api/revisions/{dr_rev['id']}/document", json={"sections": dr_sections}, headers={"X-Actor": "kanphong"})

        # 6. DB design
        schema = c.post("/api/db-schemas", json={"project_id": pid, "name": "core", "semantic_id": "sch_core"}).json()
        pr = c.post("/api/db-tables", json={"schema_id": schema["id"], "name": "purchase_request"}).json()
        c.post("/api/db-fields", json={"table_id": pr["id"], "name": "id", "data_type": "UUID", "primary_key": True})
        ah = c.post("/api/db-tables", json={"schema_id": schema["id"], "name": "approval_history"}).json()
        c.post("/api/db-fields", json={"table_id": ah["id"], "name": "approver_id", "data_type": "VARCHAR", "length": 64, "foreign_key": True, "reference": "users.id"})
        c.post("/api/db-relations", json={"schema_id": schema["id"], "from_field_semantic_id": "fld_approval_history_approver_id", "to_field_semantic_id": "fld_purchase_request_id"})
        dd = c.get(f"/api/db-schemas/{schema['id']}/data-dictionary").json()
        check("Data dictionary from canonical schema", len(dd) == 2, f"len={len(dd)}")

        # 7. trace links: Requirement → UR → DR → DB field
        c.post("/api/traces", json={"project_id": pid, "source_semantic_id": ur_sections[0]["id"], "target_semantic_id": req["code"], "relation_type": "DERIVED_FROM"}, headers={"X-Actor": "kanphong"})
        c.post("/api/traces", json={"project_id": pid, "source_semantic_id": dr_sections[0]["id"], "target_semantic_id": ur_sections[0]["id"], "relation_type": "DERIVED_FROM"}, headers={"X-Actor": "kanphong"})
        c.post("/api/traces", json={"project_id": pid, "source_semantic_id": "fld_approval_history_approver_id", "target_semantic_id": dr_sections[0]["id"], "relation_type": "IMPLEMENTS"}, headers={"X-Actor": "kanphong"})
        check("Trace chain REQ→UR→DR→DB", True)

        # 8. snapshot DB into DR, confirm, baseline
        c.post(f"/api/revisions/{dr_rev['id']}/snapshot-database", json={"schema_id": schema["id"]})
        c.post(f"/api/revisions/{dr_rev['id']}/submit-for-review")
        c.post(f"/api/revisions/{dr_rev['id']}/confirm", headers={"X-Actor": "kanphong"})
        baseline = c.post("/api/baselines", json={"project_id": pid, "name": "Purchase Approval 1.0", "artifact_revision_ids": [ur_rev["id"], dr_rev["id"]]}, headers={"X-Actor": "kanphong"}).json()
        check("Confirm DR + baseline 1.0", len(baseline["bindings"]) == 2)
        frozen_dr = next(b for b in baseline["bindings"] if b["artifact_id"] == dr["id"])["artifact_revision_id"]

        # 9. Change request: 3 approval levels
        cr = c.post("/api/change-requests", json={"project_id": pid, "requested_change": "Approval must become 3 levels", "affected_semantic_ids": [req["code"], dr_sections[0]["id"]], "reason": "Audit policy", "target_release": "1.1", "schedule_impact": "+1d", "commercial_impact": "none"}, headers={"X-Actor": "kanphong"}).json()
        check("Create CR with affected links", cr["code"] == "CR-0001")
        impact = c.get(f"/api/projects/{pid}/impact-analysis/{req['code']}?depth=2").json()
        check("Impact identifies UR/DR", any(p[-1]["semantic_id"] == dr_sections[0]["id"] for p in impact["paths"]["upstream"]))

        # 10. implement → clone DR revision
        impl = c.post(f"/api/change-requests/{cr['id']}/implement", json={"artifact_revision_map": {dr["id"]: {"note": "3 approval levels"}}}, headers={"X-Actor": "kanphong"}).json()
        new_dr_rev = impl["spawned_revisions"][0]
        check("CR spawns new DR revision", new_dr_rev["revision_number"] == 2)

        # 11. modify design: DR document 3 levels + DB field for 3rd approver
        c.put(f"/api/revisions/{new_dr_rev['revision_id']}/document", json={"sections": [{
            "id": dr_sections[0]["id"], "heading": "Approval workflow",
            "blocks": [{"kind": "numbered_list", "items": ["Manager review", "Finance review", "Director review"]}],
        }]}, headers={"X-Actor": "kanphong"})
        c.post("/api/db-fields", json={"table_id": ah["id"], "name": "director_approver_id", "data_type": "VARCHAR", "length": 64, "foreign_key": True, "reference": "users.id"})
        c.post(f"/api/revisions/{new_dr_rev['revision_id']}/snapshot-database", json={"schema_id": schema["id"]})

        # 12. semantic diff 2 → 3 levels
        diff = c.get(f"/api/revisions/{frozen_dr}/diff/{new_dr_rev['revision_id']}").json()
        doc_changed = any(c["object"] == "SECTION" and c["kind"] == "CHANGED" and c["semantic_id"] == dr_sections[0]["id"] for c in diff["document_diff"])
        db_added = any(c["object"] == "FIELD" and c["kind"] == "ADDED" and c["semantic_id"] == "fld_approval_history_director_approver_id" for c in diff["database_diff"])
        check("Semantic diff shows document change", doc_changed)
        check("Semantic diff shows DB field added", db_added)

        # 13. old baseline reproducible
        resolved = c.get(f"/api/baselines/{baseline['id']}").json()
        old_dr_binding = next(b for b in resolved["bindings"] if b["artifact_id"] == dr["id"])
        check("Old baseline keeps DR rev 1", old_dr_binding["artifact_revision_id"] == frozen_dr)
        old_doc = c.get(f"/api/revisions/{frozen_dr}/document").json()
        old_content = old_doc["sections"][0].get("content", {})
        old_items = []
        for node in old_content.get("content", []):
            if node.get("type") == "orderedList":
                for item in node.get("content", []):
                    for p in item.get("content", []):
                        old_items.extend(t.get("text") for t in p.get("content", []) if t.get("type") == "text")
        check("Old baseline DR still 2 levels", len(old_items) == 2, f"items={old_items}")

        # 14. review + confirm new revision + new baseline
        c.post(f"/api/revisions/{new_dr_rev['revision_id']}/submit-for-review")
        c.post(f"/api/revisions/{new_dr_rev['revision_id']}/confirm", json={"comment": "3 levels approved"}, headers={"X-Actor": "kanphong"})
        new_baseline = c.post("/api/baselines", json={"project_id": pid, "name": "Purchase Approval 1.1", "artifact_revision_ids": [ur_rev["id"], new_dr_rev["revision_id"]]}, headers={"X-Actor": "kanphong"}).json()
        check("New baseline confirmed", len(new_baseline["bindings"]) == 2)

        # 15. traceability remains valid
        graph = c.get(f"/api/projects/{pid}/trace-graph").json()
        check("Traceability remains valid", len(graph["edges"]) >= 4, f"edges={len(graph['edges'])}")

    print()
    failed = [r for r in results if not r[1]]
    print(f"P1 dogfood: {len(results) - len(failed)}/{len(results)} steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
