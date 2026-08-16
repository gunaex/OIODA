"""
Conductor Again — Local AI Control Center Client / AI Execution Gateway (E8-D, E8.1-C)

Sole HTTP boundary between Conductor Main and Local AI Control Center (LACC).
Conductor does not call AI providers directly, and does not select or hold raw
provider credentials — every AI execution path goes through this client:

  - EngineeringWorkPackage dispatch -> LACC's real Idea -> Code integration
    boundary (POST /api/integration/v1/work-packages), REAL_RUNTIME.
  - General AI capability execution (deliberation, skills, multi-AI, golden
    flow) -> LACC's generic AI execution boundary (POST /api/ai/execute),
    added in E8.1-B specifically to close the gap E8 disclosed
    (LACC previously had "AI_EXECUTION_REQUEST_LIVE=NOT_APPLICABLE_NO_RUNTIME_PRODUCER").
    Also REAL_RUNTIME now — live-verified end to end (Account Again entitlement,
    real Ollama execution, real usage record) while building this client.

`execute_capability()` authenticates as CONDUCTOR_MAIN via the same
AccountAgainClient service token used for entitlement/credential calls (E5.1
mechanism) and fails closed (never a direct provider SDK call) if LACC is
unavailable or denies the request.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.integration.account_again_client import AccountAgainClient, AccountAgainUnavailableError

LACC_URL = os.getenv("LOCAL_AI_CONTROL_CENTER_URL", "http://localhost:9191/api")
TIMEOUT_SECONDS = 10.0


class LACCUnavailableError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


PRIORITY_MAP = {"CRITICAL": "P0", "HIGH": "P1", "MEDIUM": "P2", "LOW": "P3"}


class LocalAIControlCenterClient:
    """CONDUCTOR_MAIN's client for Local AI Control Center."""

    @staticmethod
    def health() -> bool:
        try:
            resp = httpx.get(f"{LACC_URL}/integration/status", timeout=TIMEOUT_SECONDS)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    # ── Engineering dispatch (E8-E's real Idea -> Code boundary) ─────

    @staticmethod
    def dispatch_engineering_work_package(
        *, engineering_work_package: dict[str, Any], delivery_work_package: dict[str, Any],
        project_name: str,
    ) -> dict[str, Any]:
        """Adapts canonical EngineeringWorkPackage -> LACC's own DeliveryWorkPackageV1
        local contract shape (LACC is NOT the canonical authority; this is an explicit
        adapter, per §41/§44 — LACC's local v1 contract differs field-for-field from
        AGAIN-ECOSYSTEM's canonical v1) and POSTs to LACC's real inbound endpoint."""
        constraints = engineering_work_package.get("constraints") or {}
        priority = PRIORITY_MAP.get(delivery_work_package.get("priority", "MEDIUM"), "P2")
        body = {
            "schemaVersion": "1.0",
            "workPackageId": delivery_work_package["workPackageId"],
            "correlationId": engineering_work_package["correlationId"],
            "sourceSystem": "CONDUCTOR_MAIN",
            "targetCapability": "ENGINEERING",
            "project": {"id": delivery_work_package["workPackageId"], "name": project_name},
            "goal": engineering_work_package["requirements"],
            "businessContext": delivery_work_package.get("description", ""),
            "requirements": [engineering_work_package["requirements"]],
            "constraints": [f"{k}={v}" for k, v in constraints.items()],
            "businessAcceptanceCriteria": (delivery_work_package.get("qaContext") or {}).get(
                "businessAcceptanceCriteria", []
            ),
            "priority": priority,
            "risk": "MEDIUM",
            "dependencies": delivery_work_package.get("dependencies", []),
            "requestedOutputs": ["repo", "branch", "commit", "testResults"],
            "metadata": {"engineeringWorkPackageId": engineering_work_package["engineeringWorkPackageId"]},
            "createdAt": engineering_work_package.get("createdAt", _now_iso()),
        }
        try:
            resp = httpx.post(f"{LACC_URL}/integration/v1/work-packages", json=body, timeout=TIMEOUT_SECONDS)
        except httpx.HTTPError as e:
            raise LACCUnavailableError(f"Local AI Control Center unreachable: {e}") from e
        if resp.status_code not in (200, 201):
            raise LACCUnavailableError(f"Work package dispatch rejected: {resp.status_code} {resp.text}")
        return resp.json()

    @staticmethod
    def get_engineering_run(engineering_run_id: str) -> Optional[dict[str, Any]]:
        try:
            resp = httpx.get(f"{LACC_URL}/idea-to-code", timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise LACCUnavailableError(f"Local AI Control Center unreachable: {e}") from e
        for run in resp.json().get("runs", []):
            if run.get("engineeringRunId") == engineering_run_id or run.get("id") == engineering_run_id:
                return run
        return None

    @staticmethod
    def start_engineering_run(engineering_run_id: str) -> dict[str, Any]:
        try:
            resp = httpx.post(
                f"{LACC_URL}/idea-to-code",
                json={"action": "start", "engineeringRunId": engineering_run_id},
                timeout=60.0,
            )
        except httpx.HTTPError as e:
            raise LACCUnavailableError(f"Local AI Control Center unreachable: {e}") from e
        return resp.json()

    @staticmethod
    def get_handoff_artifacts(engineering_run_id: str) -> list[dict[str, Any]]:
        try:
            resp = httpx.get(f"{LACC_URL}/idea-to-code/{engineering_run_id}/handoff", timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            return resp.json().get("artifacts", [])
        except httpx.HTTPError:
            return []

    # ── General AI capability execution — the AIExecutionGateway (E8.1-C) ────

    @staticmethod
    def execute_capability(
        *, capability: str, correlation_id: str, prompt: str, tenant_id: str = "local-tenant",
        request_id: Optional[str] = None, idempotency_key: Optional[str] = None,
        model_preference: Optional[str] = None,
    ) -> dict[str, Any]:
        """The single AIExecutionGateway boundary: every real Conductor AI execution
        path (deliberation, skills, multi-AI, golden flow) calls this, never a
        provider SDK directly. `capability` MUST be one of the canonical
        AIExecutionRequest.capability values (CODE_PLANNING, GENERAL_REASONING, etc.
        — NOT Account Again's AI_* entitlement vocabulary; LACC's /api/ai/execute
        translates between the two internally).

        Fails closed to BLOCKED_BY_POLICY/FAILED — NEVER falls back to a direct
        provider SDK call (LACC_DOWN_NO_DIRECT_PROVIDER_BYPASS)."""
        request_id = request_id or f"req-{uuid.uuid4().hex[:12]}"
        body = {
            "requestId": request_id,
            "correlationId": correlation_id,
            "capability": capability,
            "tenantId": tenant_id,
            "payload": {"prompt": prompt},
        }
        if idempotency_key:
            body["idempotencyKey"] = idempotency_key
        if model_preference:
            body["modelPreference"] = {"model": model_preference}

        try:
            token = AccountAgainClient.get_service_token()
        except AccountAgainUnavailableError as e:
            return {
                "requestId": request_id, "correlationId": correlation_id, "status": "FAILED",
                "outputSummary": f"Cannot authenticate to Local AI Control Center: {e}",
                "providerUsed": "none", "modelUsed": "none", "completedAt": _now_iso(),
            }

        try:
            resp = httpx.post(
                f"{LACC_URL}/ai/execute", json=body,
                headers={"Authorization": f"Bearer {token}"}, timeout=60.0,
            )
            return resp.json()
        except httpx.HTTPError as e:
            return {
                "requestId": request_id, "correlationId": correlation_id, "status": "FAILED",
                "outputSummary": f"AI_EXECUTION_UNAVAILABLE: Local AI Control Center unreachable: {e}",
                "providerUsed": "none", "modelUsed": "none", "completedAt": _now_iso(),
            }
