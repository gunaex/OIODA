"""
E8.1-I — Real legacy deliberation golden flow.

Proves a REAL pre-existing Conductor feature (multi-agent deliberation) now runs its
AI execution through the AIExecutionGateway end to end: real Account Again
entitlement, real local Ollama execution across multiple independent panel members,
real usage records, and a complete evidence chain — with zero direct provider calls.
"""

import httpx
import pytest

from app.integration.account_again_client import AccountAgainClient
from app.integration.lacc_client import LocalAIControlCenterClient

ACCOUNT_AGAIN_UP = AccountAgainClient.health()
LACC_UP = LocalAIControlCenterClient.health()

pytestmark = pytest.mark.skipif(
    not (ACCOUNT_AGAIN_UP and LACC_UP), reason="Account Again / Local AI Control Center not reachable"
)


@pytest.fixture
def deliberation_setup(client, auth_headers):
    """Seeds enough AIResource rows for a 3-member panel (metadata only — no real
    provider credential is used at execution time, per E8.1-G)."""
    from app.database import MasterSessionLocal
    from app.models import AIAccount, AIExecutionRuntime, AIProvider, AIResource, InstalledModel

    db = MasterSessionLocal()
    provider = AIProvider(code="local-e81", name="Local E8.1")
    db.add(provider)
    db.flush()
    for i in range(3):
        account = AIAccount(provider_id=provider.id, name=f"e81-acc-{i}", access_mode="LOCAL_MODEL")
        db.add(account)
        db.flush()
        runtime = AIExecutionRuntime(account_id=account.id, runtime_type="LOCAL_SERVER")
        db.add(runtime)
        db.flush()
        model = InstalledModel(runtime_id=runtime.id, model_id=f"e81-model-{i}", display_name=f"e81-model-{i}")
        db.add(model)
        db.flush()
        db.add(AIResource(
            account_id=account.id, runtime_id=runtime.id, model_id=model.id,
            display_name=f"e81-res-{i}", health_state="AVAILABLE",
        ))
    db.commit()
    db.close()


def test_golden_deliberation_real_flow_via_lacc(client, auth_headers, deliberation_setup):
    start = client.post("/api/deliberation/start", json={
        "title": "E8.1 golden: SQLite vs Postgres for a small local service",
        "task": "Compare using SQLite vs PostgreSQL for a small internal service with "
                "under 100 daily users. Recommend one.",
        "criteria": "Lowest operational overhead wins, given the low traffic.",
        "min_members": 3,
    }, headers=auth_headers)
    assert start.status_code == 200, start.text
    case = start.json()
    case_id = case["case_id"]
    assert case["panel_size"] >= 3

    generated = []
    for member in case["members"]:
        resp = client.post(
            f"/api/deliberation/{case_id}/members/{member['id']}/generate", headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        generated.append(resp.json())

    # ── Multi-participant: at least two genuinely different local models used ──
    models_used = {g["model"] for g in generated}
    assert len(models_used) >= 2, f"expected model diversity across panel, got {models_used}"
    for g in generated:
        assert g["provider"] == "ollama"  # real local executor, never a cloud SDK call

    # ── Case reached independent_complete after all members submitted ──
    assert generated[-1]["all_submitted"] is True
    assert generated[-1]["case_status"] == "independent_complete"

    # ── Evidence chain: each generation has requestId, correlationId, evidenceRef ──
    for g in generated:
        assert g["requestId"]
        assert g["correlationId"] == f"corr-delib-{case_id}"
        assert g["evidenceRef"], "usage evidence must be recorded via Account Again"

    # ── Usage actually reached Account Again (real record, not fabricated) ──
    all_usage = httpx.get("http://localhost:8001/api/v1/usage", timeout=10.0).json()
    correlation_ids_seen = {u.get("correlationId") for u in all_usage}
    assert f"corr-delib-{case_id}" in correlation_ids_seen

    # ── Case detail view reflects real submissions, not placeholders ──
    detail = client.get(f"/api/deliberation/{case_id}", headers=auth_headers)
    assert detail.status_code == 200
    submissions = detail.json().get("submissions", [])
    assert len(submissions) >= 3
    for s in submissions:
        assert s.get("conclusion")
