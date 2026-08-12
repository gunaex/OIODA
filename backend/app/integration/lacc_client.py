"""
Conductor Again — Local AI Control Center Client (E8-D)

Sole HTTP boundary between Conductor Main and Local AI Control Center (LACC).
Conductor no longer calls AI providers directly for engineering execution —
EngineeringWorkPackage dispatch goes through LACC's real Idea -> Code
integration boundary (POST /api/integration/v1/work-packages), which is a
genuine REAL_RUNTIME endpoint verified live against a running LACC instance.

Disclosed interface gap (not a Conductor bug): LACC exposes NO generic
AIExecutionRequest/AIExecutionResult execution endpoint for a Specialist OS's
own general-reasoning needs (Conductor's deliberation/decomposition). LACC's
own contract-conformance-v2 route reports this same gap as
"AI_EXECUTION_REQUEST_LIVE=NOT_APPLICABLE_NO_RUNTIME_PRODUCER". Per E8 task
policy (§36 "prefer Conductor-side adaptation" / do not build missing LACC
surface as a side effect), `execute_capability` below does NOT invent a
provider call to fill that gap — it fails closed with BLOCKED_BY_POLICY, the
same discipline LACC's own client applies to Account Again failures. It never
falls back to a direct AI provider SDK call.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

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

    # ── General AI capability execution (E8-D §36-38) ─────────────────

    @staticmethod
    def execute_capability(
        *, capability: str, correlation_id: str, payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Provider-neutral AIExecutionRequest -> AIExecutionResult. LACC has no
        generic execution endpoint for this today (disclosed interface gap, module
        docstring). Fails closed to BLOCKED_BY_POLICY — NEVER falls back to a direct
        provider SDK call (LACC_DOWN_NO_DIRECT_PROVIDER_BYPASS)."""
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        return {
            "requestId": request_id,
            "correlationId": correlation_id,
            "status": "BLOCKED_BY_POLICY",
            "outputSummary": (
                "Local AI Control Center exposes no generic AIExecutionRequest execution "
                "endpoint for this capability. Conductor does not fall back to a direct "
                "AI provider call — see LACC_INTERFACE_GAP in the E8 report."
            ),
            "providerUsed": "none",
            "modelUsed": "none",
            "policyResult": {"airlockDecision": "BLOCK"},
            "completedAt": _now_iso(),
        }
