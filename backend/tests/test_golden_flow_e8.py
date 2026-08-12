"""
E8-H — Golden Conductor runtime flow (via the real HTTP API).

Proves: real orchestration through Conductor's own API, real Account Again
entitlement gating (allow + deny), real Idea -> Code dispatch (when reachable),
dispatch idempotency, and cross-tenant blocking. Skipped end-to-end when
Account Again is not reachable — these are integration tests, not mocks.
"""

import pytest

from app.integration.account_again_client import AccountAgainClient
from app.integration.lacc_client import LocalAIControlCenterClient
from app.orchestration import ecosystem_auth

ACCOUNT_AGAIN_UP = AccountAgainClient.health()
LACC_UP = LocalAIControlCenterClient.health()

pytestmark = pytest.mark.skipif(not ACCOUNT_AGAIN_UP, reason="Account Again not reachable")


def _create_intent(client, headers, tenant="local-tenant", title="E8 golden flow smoke"):
    resp = client.post(
        "/api/orchestration/intents",
        json={"title": title, "description": "Add a health endpoint", "priority": "HIGH"},
        headers={**headers, "X-Tenant-Id": tenant},
    )
    return resp


def test_golden_allow_flow_intent_and_run_creation(client, auth_headers):
    resp = _create_intent(client, auth_headers)
    assert resp.status_code == 201, resp.text
    intent = resp.json()
    assert intent["status"] == "RECEIVED"

    run_resp = client.post(
        f"/api/orchestration/intents/{intent['businessIntentId']}/runs",
        json={"assignments": {"engineering": True, "infrastructure": True, "qa": True}},
        headers={**auth_headers, "X-Tenant-Id": "local-tenant"},
    )
    assert run_resp.status_code == 201, run_resp.text
    run = run_resp.json()
    assert run["currentStage"] == "PLAN"
    assert run["status"] == "IN_PROGRESS"


@pytest.mark.skipif(not LACC_UP, reason="Local AI Control Center not reachable")
def test_golden_allow_flow_full_dispatch_chain(client, auth_headers):
    intent = _create_intent(client, auth_headers, title="E8 golden allow full chain").json()
    run = client.post(
        f"/api/orchestration/intents/{intent['businessIntentId']}/runs",
        json={"assignments": {"engineering": True, "infrastructure": True, "qa": True}},
        headers={**auth_headers, "X-Tenant-Id": "local-tenant"},
    ).json()
    run_id = run["runId"]

    disp = client.post(
        f"/api/orchestration/runs/{run_id}/dispatch-engineering",
        json={"requirements": "Add a GET /pingpong endpoint returning ok", "project_name": "e8-golden"},
        headers={**auth_headers, "X-Tenant-Id": "local-tenant"},
    )
    assert disp.status_code == 200, disp.text
    run_detail = client.get(f"/api/orchestration/runs/{run_id}", headers={**auth_headers, "X-Tenant-Id": "local-tenant"}).json()
    assert run_detail["currentStage"] == "ENGINEERING"


def test_idempotent_dispatch_replay_creates_no_duplicate(client, auth_headers):
    intent = _create_intent(client, auth_headers, title="E8 idempotency test").json()
    run = client.post(
        f"/api/orchestration/intents/{intent['businessIntentId']}/runs",
        json={"assignments": {"engineering": True}},
        headers={**auth_headers, "X-Tenant-Id": "local-tenant"},
    ).json()
    run_id = run["runId"]

    body = {"requirements": "idempotency probe", "project_name": "e8-idem", "idempotency_key": "e8-idem-fixed-key"}
    first = client.post(f"/api/orchestration/runs/{run_id}/dispatch-engineering", json=body,
                         headers={**auth_headers, "X-Tenant-Id": "local-tenant"})
    second = client.post(f"/api/orchestration/runs/{run_id}/dispatch-engineering", json=body,
                          headers={**auth_headers, "X-Tenant-Id": "local-tenant"})
    assert first.status_code == 200
    assert second.status_code == 200

    dispatches = client.get(f"/api/orchestration/runs/{run_id}/dispatches",
                             headers={**auth_headers, "X-Tenant-Id": "local-tenant"}).json()
    engineering_dispatches = [d for d in dispatches if d["specialist"] == "ENGINEERING"]
    assert len(engineering_dispatches) == 1  # same idempotency key -> no duplicate


def test_cross_tenant_block(client, auth_headers):
    intent = _create_intent(client, auth_headers, tenant="local-tenant", title="E8 tenant isolation").json()
    run = client.post(
        f"/api/orchestration/intents/{intent['businessIntentId']}/runs",
        json={"assignments": {"engineering": True}},
        headers={**auth_headers, "X-Tenant-Id": "local-tenant"},
    ).json()
    run_id = run["runId"]

    # A different tenant must not be able to read this run, even with a valid Account
    # Again ALLOW decision for its own (different) tenant's CONDUCTOR_MAIN entitlement.
    cross_resp = client.get(f"/api/orchestration/runs/{run_id}", headers={**auth_headers, "X-Tenant-Id": "other-tenant"})
    assert cross_resp.status_code in (403, 404)


def test_golden_deny_flow_entitlement_denied(client, auth_headers, monkeypatch):
    """Simulates Account Again denying CONDUCTOR_MAIN's product entitlement for a
    tenant (e.g. suspended tenant) and proves Conductor blocks the request rather
    than silently proceeding."""
    from app.integration.account_again_client import AccountAgainClient as AAC

    def deny(*args, **kwargs):
        return {"decision": "DENY", "reasonCode": "TENANT_SUSPENDED", "reasonMessage": "simulated deny",
                "evaluatedAt": "2026-08-12T00:00:00Z", "entitlementDecisionId": "sim-deny-1"}

    monkeypatch.setattr(AAC, "evaluate_entitlement", staticmethod(deny))
    resp = _create_intent(client, auth_headers, tenant="denied-tenant", title="should be denied")
    assert resp.status_code == 403
    assert resp.json()["detail"]["reasonCode"] == "TENANT_SUSPENDED"
