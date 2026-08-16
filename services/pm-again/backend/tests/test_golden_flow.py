"""PM-E8 — golden integration flow, exercised through PM Again's real code
paths end-to-end (intake -> mapping -> real task state changes -> PMStatus
-> idempotency -> tenant isolation -> auth rejection). Conductor's identity
is simulated via dependency override (same technique used throughout
PM-E4/E6's tests) rather than a live three-process run — see
docs/current-state/PM_ECOSYSTEM_INTEGRATION.md for what this does and does
not prove about the live cross-service network path."""

from app.main import app
from app.ecosystem.service_auth import require_conductor_service_identity
from app.contracts.validator import CanonicalContractValidator

_pmstatus_validator = CanonicalContractValidator("PMStatus")

GOLDEN_CORRELATION_ID = "e2e-golden-001"
GOLDEN_WORK_PACKAGE_ID = "wp-golden-001"
GOLDEN_BUSINESS_INTENT_ID = "bi-golden-001"

GOLDEN_DWP = {
    "workPackageId": GOLDEN_WORK_PACKAGE_ID,
    "correlationId": GOLDEN_CORRELATION_ID,
    "businessIntentId": GOLDEN_BUSINESS_INTENT_ID,
    "title": "Minimal local service with a health endpoint and tests",
    "priority": "HIGH",
    "state": "PLANNED",
    "assignments": {"pm": True, "engineering": True},
    "createdAt": "2026-08-12T00:00:00Z",
}


def _as_conductor(tenant_id="golden-tenant"):
    app.dependency_overrides[require_conductor_service_identity] = lambda: {
        "systemId": "CONDUCTOR_MAIN",
        "tenantId": tenant_id,
    }


def teardown_function(_fn):
    app.dependency_overrides.pop(require_conductor_service_identity, None)


def test_golden_flow_end_to_end(client, admin_user):
    # 1. Conductor dispatches the DeliveryWorkPackage.
    _as_conductor()
    intake_resp = client.post("/api/ecosystem/delivery-work-packages", json=GOLDEN_DWP)
    assert intake_resp.status_code == 200, intake_resp.text
    intake_body = intake_resp.json()
    assert intake_body["created"] is True
    assert intake_body["correlationId"] == GOLDEN_CORRELATION_ID
    slug = intake_body["projectSlug"]
    assert slug

    # 2. PM Again produced real project/task state — fetch PMStatus by
    #    workPackageId (the identifier Conductor actually holds).
    status_resp = client.get("/api/ecosystem/pm-status", params={"workPackageId": GOLDEN_WORK_PACKAGE_ID})
    assert status_resp.status_code == 200, status_resp.text
    status = status_resp.json()
    _pmstatus_validator.validate(status)
    assert status["workPackageId"] == GOLDEN_WORK_PACKAGE_ID
    assert status["correlationId"] == GOLDEN_CORRELATION_ID
    assert status["projectStatus"] in ("NOT_STARTED", "IN_PROGRESS")
    assert len(status["tasks"]) == 1
    seed_task_id = status["tasks"][0]["id"]

    # 3. Real PM state change: Todo -> InProgress -> Done, as a human
    #    operator working the project.
    login = client.post("/api/auth/login", json={"email": "pmo@test.local", "password": "test-password-123"})
    assert login.status_code == 200
    task_list = client.get(f"/api/{slug}/tasks").json()
    task = task_list[0]
    client.put(f"/api/{slug}/tasks/{task['id']}", json={"title": task["title"], "status": "InProgress"})

    status_resp2 = client.get("/api/ecosystem/pm-status", params={"workPackageId": GOLDEN_WORK_PACKAGE_ID})
    status2 = status_resp2.json()
    assert status2["projectStatus"] == "IN_PROGRESS"
    assert status2["tasks"][0]["status"] == "InProgress"
    assert status2["tasks"][0]["id"] == seed_task_id
    _pmstatus_validator.validate(status2)

    client.put(f"/api/{slug}/tasks/{task['id']}", json={"title": task["title"], "status": "Done"})
    status_resp3 = client.get("/api/ecosystem/pm-status", params={"workPackageId": GOLDEN_WORK_PACKAGE_ID})
    status3 = status_resp3.json()
    assert status3["projectStatus"] == "COMPLETED"
    _pmstatus_validator.validate(status3)

    # 4. Blocker flow: a real open issue makes PMStatus BLOCKED (non-final —
    #    Conductor readiness policy, not PM Again, decides delivery outcome).
    issue_resp = client.post(
        f"/api/{slug}/board-items",
        json={"item_type": "issue", "title": "Health endpoint returns 500 under load", "severity": "High"},
    )
    assert issue_resp.status_code == 200
    status_resp4 = client.get("/api/ecosystem/pm-status", params={"workPackageId": GOLDEN_WORK_PACKAGE_ID})
    status4 = status_resp4.json()
    assert status4["projectStatus"] == "BLOCKED"
    assert len(status4["blockers"]) == 1
    _pmstatus_validator.validate(status4)

    # 5. Idempotency: replay the exact same DeliveryWorkPackage.
    _as_conductor()
    replay_resp = client.post("/api/ecosystem/delivery-work-packages", json=GOLDEN_DWP)
    assert replay_resp.status_code == 200
    replay_body = replay_resp.json()
    assert replay_body["created"] is False
    assert replay_body["externalWorkReferenceId"] == intake_body["externalWorkReferenceId"]
    assert replay_body["projectSlug"] == slug

    # 6. Cross-tenant deny: a different tenant cannot claim the same
    #    businessIntentId's project.
    _as_conductor(tenant_id="a-different-tenant")
    deny_resp = client.post(
        "/api/ecosystem/delivery-work-packages",
        json=dict(GOLDEN_DWP, workPackageId="wp-golden-002"),
    )
    assert deny_resp.status_code == 403

    # 7. Invalid / missing service token rejected.
    app.dependency_overrides.pop(require_conductor_service_identity, None)
    missing_resp = client.post("/api/ecosystem/delivery-work-packages", json=GOLDEN_DWP)
    assert missing_resp.status_code == 401
    invalid_resp = client.post(
        "/api/ecosystem/delivery-work-packages",
        json=GOLDEN_DWP,
        headers={"Authorization": "Bearer garbage"},
    )
    assert invalid_resp.status_code == 403

    # 8. Evidence chain: correlation id is preserved end-to-end, and the
    #    project's ecosystem-source record is visible/truthful in the UI API.
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    source_resp = client.get(f"/api/{slug}/ecosystem-source")
    assert source_resp.status_code == 200
    source = source_resp.json()
    assert source["correlationId"] == GOLDEN_CORRELATION_ID
    assert source["sourceSystem"] == "CONDUCTOR_MAIN"
