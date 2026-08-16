#!/usr/bin/env python
"""P3 cross-product dogfood — ecosystem-connected design authority.

Scenario: an approval workflow is designed, confirmed, baselined, then
handed off to PM Again and QA Again through the durable outbox, linked to
external PM/QA objects, exported (OpenAPI + xlsx/docx/package V2), and the
historical baseline is shown to be reproducible after a later design change.

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


OPENAPI_DOC = """
openapi: 3.0.0
info: {title: Approvals, version: "1.0"}
paths:
  /approvals:
    post:
      summary: Create approval request
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [amount]
              properties:
                amount: {type: number}
      responses:
        "201": {description: Created}
        "400": {description: Bad request}
"""


def main() -> int:
    with TestClient(app) as c:
        H = {"X-Actor": "kanphong", "X-Account-Id": "acc-kanphong", "X-Actor-Name": "Kanphong", "X-Tenant-Id": "t-main"}

        # 1. Project + requirement
        p = c.post("/api/projects", json={"key": "ECO3", "name": "Ecosystem Approval"}, headers=H).json()
        pid = p["id"]
        check("Create project", bool(pid))
        req = c.post("/api/requirements", json={"project_id": pid, "title": "Approvals need PM+QA handoff", "priority": "MUST"}, headers=H).json()
        check("Create requirement", req["code"] == "REQ-0001")

        # 2. UR confirm
        ur = c.post("/api/artifacts", json={"project_id": pid, "type": "UR", "title": "UR — Approval"}, headers=H).json()
        ur_rev = ur["revisions"][0]
        c.post(f"/api/revisions/{ur_rev['id']}/submit-for-review")
        c.post(f"/api/revisions/{ur_rev['id']}/confirm", json={"comment": "ok"}, headers=H)
        check("UR confirmed", c.get(f"/api/revisions/{ur_rev['id']}").json()["status"] == "CONFIRMED")

        # 3. Structured design: DB + API + flow
        schema = c.post("/api/db-schemas", json={"project_id": pid, "name": "core", "semantic_id": "sch_core"}).json()
        tbl = c.post("/api/db-tables", json={"schema_id": schema["id"], "name": "approval"}).json()
        c.post("/api/db-fields", json={"table_id": tbl["id"], "name": "id", "data_type": "UUID", "primary_key": True})
        ep = c.post("/api/api-endpoints", json={"project_id": pid, "method": "POST", "path": "/approvals", "summary": "Create approval"}, headers=H).json()
        flow = c.post("/api/flows", json={"project_id": pid, "name": "Approval Flow", "semantic_id": "flow_approval"}).json()
        c.post("/api/flow-steps", json={"flow_id": flow["id"], "name": "Submit", "semantic_id": "flow_step_submit", "step_type": "START"})
        c.post("/api/flow-steps", json={"flow_id": flow["id"], "name": "Approved", "semantic_id": "flow_step_approved", "step_type": "END"})
        check("Structured design created", bool(ep.get("id")) and bool(flow.get("id")))

        # 4. DR confirm snapshots technical design
        dr = c.post("/api/artifacts", json={"project_id": pid, "type": "DR", "title": "DR — Approval"}, headers=H).json()
        dr_rev = dr["revisions"][0]
        c.post(f"/api/revisions/{dr_rev['id']}/submit-for-review")
        c.post(f"/api/revisions/{dr_rev['id']}/confirm", json={"comment": "DR ok"}, headers=H)
        dr_json = c.get(f"/api/revisions/{dr_rev['id']}").json()
        check("DR confirmed with technical design", dr_json["status"] == "CONFIRMED" and "api_endpoints" in dr_json.get("snapshot", {}).get("technical_design", {}))

        # 5. Baseline
        baseline = c.post("/api/baselines", json={"project_id": pid, "name": "Approval 1.0", "artifact_revision_ids": [ur_rev["id"], dr_rev["id"]]}, headers=H).json()
        check("Baseline frozen", len(baseline["bindings"]) == 2)

        # 6. PM handoff -> durable outbox
        pmh = c.post("/api/handoffs/execution", json={"project_id": pid, "baseline_id": baseline["id"], "source_revision_id": dr_rev["id"]}, headers=H).json()
        check("PM handoff created", pmh["target_service"] == "pm-again" and pmh["status"] == "DRAFT")
        outbox = c.get("/api/outbox").json()
        pm_out = [o for o in outbox if o["target_service"] == "pm-again"]
        check("PM outbox event queued", any(o["status"] == "PENDING" for o in pm_out), f"pm_out={pm_out}")

        # 7. QA handoff -> durable outbox
        qah = c.post("/api/handoffs/qa", json={"project_id": pid, "baseline_id": baseline["id"], "requirement_ids": ["REQ-0001"], "target_release": "1.0"}, headers=H).json()
        outbox = c.get("/api/outbox").json()
        qa_out = [o for o in outbox if o["target_service"] == "qa-again"]
        check("QA outbox event queued", any(o["status"] == "PENDING" for o in qa_out))

        # 8. External reference (PM task)
        ext = c.post("/api/external-references", json={"project_id": pid, "semantic_id": "REQ-0001", "service": "pm-again", "external_id": "PM-42", "relation_type": "IMPLEMENTED_BY", "object_type": "task"}).json()
        check("External reference linked", ext["external_id"] == "PM-42")
        refs = c.get(f"/api/projects/{pid}/external-references").json()
        check("External reference list", len(refs) == 1)

        # 9. Impact analysis v2 + change set
        cs = c.post("/api/change-sets", json={"project_id": pid, "name": "Add Director review", "items": [{"semantic_id": "REQ-0001", "change_type": "MODIFIED"}]}, headers=H).json()
        check("Change set created", len(cs["items"]) == 1)
        impact = c.get(f"/api/projects/{pid}/impact-v2/REQ-0001").json()
        check("Impact v2 returns affected list", "affected" in impact)

        # 10. OpenAPI import + export
        imp = c.post("/api/openapi/import", json={"project_id": pid, "document": OPENAPI_DOC}, headers=H).json()
        check("OpenAPI imported", len(imp["applied"]) == 1)
        oas = c.get(f"/api/revisions/{dr_rev['id']}/openapi").json()
        check("OpenAPI export reconstructs paths", "/approvals" in oas["paths"])

        # 11. Export V2 (xlsx, docx, package)
        xlsx = c.get(f"/api/revisions/{dr_rev['id']}/export?format=xlsx")
        check("XLSX export", xlsx.content[:2] == b"PK")
        docx = c.get(f"/api/revisions/{dr_rev['id']}/export?format=docx")
        check("DOCX export", docx.content[:2] == b"PK")
        pkg2 = c.get(f"/api/baselines/{baseline['id']}/package-v2")
        check("Design package V2 export", pkg2.content[:2] == b"PK")

        # 12. Ecosystem timeline
        events = c.get(f"/api/projects/{pid}/ecosystem-events").json()
        types = {e["event_type"] for e in events}
        check("Ecosystem timeline has handoff events", {"EXECUTION_REQUESTED", "QA_VALIDATION_REQUESTED"} <= types, f"types={types}")

        # 13. Historical truth: later design change never alters the baseline
        new_dr = c.post(f"/api/artifacts/{dr['id']}/revisions", json={}, headers=H).json()
        c.post(f"/api/revisions/{new_dr['id']}/submit-for-review")
        c.post(f"/api/revisions/{new_dr['id']}/confirm", json={"comment": "v2"}, headers=H)
        old_baseline = c.get(f"/api/baselines/{baseline['id']}").json()
        dr_bind = next(b for b in old_baseline["bindings"] if b["artifact_id"] == dr["id"])
        check("Baseline still binds DR rev 1", dr_bind["artifact_revision_id"] == dr_rev["id"])
        old_oas = c.get(f"/api/revisions/{dr_rev['id']}/openapi").json()
        check("Historical OpenAPI reproducible", "/approvals" in old_oas["paths"])

    print()
    failed = [r for r in results if not r[1]]
    print(f"P3 dogfood: {len(results) - len(failed)}/{len(results)} steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
