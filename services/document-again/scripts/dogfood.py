#!/usr/bin/env python
"""P0 dogfood scenario — exercises the full first flow end to end
against the real backend database via the HTTP API.

Flow: Create Project → Requirement → UR → review → annotate → confirm
→ DR → trace to requirement → DB table/field → confirm DR baseline
→ Change Request → new revisions → old baseline untouched.
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
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail and not cond else ""))


def main() -> int:
    with TestClient(app) as c:
        # 1. Create project -------------------------------------------------
        project = c.post("/api/projects", json={
            "key": "ORDERS", "name": "Order Approval System",
            "description": "Dogfood project for Document Again P0",
        }, headers={"X-Actor": "kanphong"}).json()
        pid = project["id"]
        check("Create project", bool(pid))

        # 2. Create requirement ----------------------------------------------
        req = c.post("/api/requirements", json={
            "project_id": pid, "title": "Order approval history must be auditable",
            "description": "Every approval decision must be stored with actor, time and outcome.",
            "source_type": "CUSTOMER", "priority": "MUST",
        }, headers={"X-Actor": "kanphong"}).json()
        check("Create requirement", req["code"].startswith("REQ-"), req.get("code", ""))

        # 3-4. Create UR artifact + revision ----------------------------------
        ur = c.post("/api/artifacts", json={
            "project_id": pid, "type": "UR", "title": "UR — Order Approval",
            "snapshot": {"sections": [
                {"id": "overview", "requirement_codes": [req["code"]]},
                {"id": "rules", "steps": ["manager_review", "finance_review"]},
            ]},
        }, headers={"X-Actor": "kanphong"}).json()
        ur_rev1 = ur["revisions"][0]
        check("Create UR artifact + revision 1", ur_rev1["revision_number"] == 1)

        # 5. Submit for review ------------------------------------------------
        r = c.post(f"/api/revisions/{ur_rev1['id']}/submit-for-review")
        check("Submit UR for review", r.json()["status"] == "IN_REVIEW")

        # 6. Comment / annotation (semantic anchor on the requirement) ---------
        ann = c.post("/api/annotations", json={
            "project_id": pid, "anchor_object_type": "REQUIREMENT",
            "anchor_semantic_id": req["code"],
            "content": "Keep approval history for 7 years?",
            "type": "QUESTION", "canvas_x": 100, "canvas_y": 80,
        }, headers={"X-Actor": "reviewer-a"}).json()
        check("Annotate semantic object", ann["anchor_semantic_id"] == req["code"])
        c.post(f"/api/annotations/{ann['id']}/status/RESOLVED")

        # 7. Confirm UR --------------------------------------------------------
        r = c.post(f"/api/revisions/{ur_rev1['id']}/confirm",
                   json={"comment": "UR reviewed", "evidence": {"review": "walkthrough"}},
                   headers={"X-Actor": "kanphong"})
        check("Confirm UR (immutable)", r.json()["revision"]["status"] == "CONFIRMED")
        blocked = c.put(f"/api/revisions/{ur_rev1['id']}/snapshot", json={"snapshot": {"x": 1}})
        check("Confirmed UR edit rejected", blocked.status_code == 409)

        # 8-9. Create DR + link to requirement ---------------------------------
        dr = c.post("/api/artifacts", json={
            "project_id": pid, "type": "DR", "title": "DR — Order Approval",
            "snapshot": {"schema": "sch_core", "tables": []},
        }, headers={"X-Actor": "kanphong"}).json()
        dr_rev1 = dr["revisions"][0]
        dr_sec = f"sec_{dr_rev1['id']}"
        c.post("/api/semantic-objects", json={
            "project_id": pid, "semantic_id": dr_sec,
            "object_type": "DOCUMENT_SECTION", "display_name": "DR — Order Approval",
        })
        trace = c.post("/api/traces", json={
            "project_id": pid, "source_semantic_id": dr_sec,
            "target_semantic_id": req["code"], "relation_type": "DERIVED_FROM",
        }, headers={"X-Actor": "kanphong"}).json()
        check("DR traced to requirement", trace.get("relation") == "DERIVED_FROM")

        # 10. Database table / fields ------------------------------------------
        schema = c.post("/api/db-schemas", json={
            "project_id": pid, "name": "core", "semantic_id": "sch_core",
        }).json()
        users = c.post("/api/db-tables", json={
            "schema_id": schema["id"], "name": "users", "description": "Application users",
        }).json()
        c.post("/api/db-fields", json={
            "table_id": users["id"], "name": "id", "data_type": "UUID", "primary_key": True,
        })
        hist = c.post("/api/db-tables", json={
            "schema_id": schema["id"], "name": "approval_history",
            "description": "Immutable audit of approval decisions",
        }).json()
        fld = c.post("/api/db-fields", json={
            "table_id": hist["id"], "name": "approver_id", "data_type": "VARCHAR",
            "length": 64, "foreign_key": True, "reference": "users.id",
            "description": "Who approved",
        }).json()
        check("DB table + field as structured objects",
              fld["semantic_id"] == "fld_approval_history_approver_id")
        c.post("/api/db-fields", json={"table_id": hist["id"], "name": "decision", "data_type": "VARCHAR", "length": 16})
        c.post("/api/db-relations", json={
            "schema_id": schema["id"],
            "from_field_semantic_id": "fld_approval_history_approver_id",
            "to_field_semantic_id": "fld_users_id",
        })
        dictionary = c.get(f"/api/db-schemas/{schema['id']}/data-dictionary").json()
        # users.id + approval_history.{approver_id, decision} = 3 field rows
        check("Data dictionary is a view over the model", len(dictionary) == 3)

        # 11. Confirm DR baseline ------------------------------------------------
        c.post(f"/api/revisions/{dr_rev1['id']}/submit-for-review")
        c.post(f"/api/revisions/{dr_rev1['id']}/confirm", headers={"X-Actor": "kanphong"})
        baseline = c.post("/api/baselines", json={
            "project_id": pid, "name": "Order Approval 1.0",
            "description": "First confirmed UR+DR set",
            "artifact_revision_ids": [ur_rev1["id"], dr_rev1["id"]],
        }, headers={"X-Actor": "kanphong"}).json()
        check("Confirm DR + freeze baseline", len(baseline["bindings"]) == 2)
        frozen_dr = next(b for b in baseline["bindings"] if b["artifact_id"] == dr["id"])

        # 12. Change request: "Add one more approval step" ------------------------
        cr = c.post("/api/change-requests", json={
            "project_id": pid, "requested_change": "Add one more approval step (director review)",
            "affected_semantic_ids": [req["code"], dr_sec],
            "reason": "Customer escalation policy", "target_release": "1.1",
            "schedule_impact": "+2 days", "commercial_impact": "none",
        }, headers={"X-Actor": "kanphong"}).json()
        check("Create change request linked to affected objects",
              cr["code"] == "CR-0001" and len(cr["affected_semantic_ids"]) == 2)

        implemented = c.post(f"/api/change-requests/{cr['id']}/implement", json={
            "artifact_revision_map": {
                dr["id"]: {"schema": "sch_core",
                           "tables": ["users", "approval_history"],
                           "steps": ["manager_review", "finance_review", "director_review"]},
            },
        }, headers={"X-Actor": "kanphong"}).json()
        new_dr_rev = implemented["spawned_revisions"][0]
        check("CR spawns new DR revision", new_dr_rev["revision_number"] == 2)

        # Old baseline must still resolve the old DR revision --------------------
        resolved = c.get(f"/api/baselines/{baseline['id']}").json()
        dr_binding_now = next(b for b in resolved["bindings"] if b["artifact_id"] == dr["id"])
        check("Old baseline keeps DR rev 1 after v2 exists",
              dr_binding_now["artifact_revision_id"] == frozen_dr["artifact_revision_id"])
        old_rev = c.get(f"/api/revisions/{frozen_dr['artifact_revision_id']}").json()
        check("Superseded DR rev 1 still readable",
              old_rev["status"] in ("SUPERSEDED", "CONFIRMED") and "tables" in old_rev["snapshot"])
        new_rev = c.get(f"/api/revisions/{new_dr_rev['revision_id']}").json()
        check("New DR rev 2 carries the CR change",
              "director_review" in new_rev["snapshot"].get("steps", []))

        impact = c.get(f"/api/projects/{pid}/impact/{req['code']}").json()
        check("Impact via trace links", any(
            i["semantic_id"] == dr_sec for i in impact["upstream"]))

    print()
    failed = [r for r in results if not r[1]]
    print(f"Dogfood: {len(results) - len(failed)}/{len(results)} steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
