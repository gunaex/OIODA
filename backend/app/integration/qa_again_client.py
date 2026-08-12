"""
Conductor Again — QA Again Client (QA-E5)

HTTP boundary between Conductor Main and QA Again. Mirrors
pm_again_client.py's shape and philosophy: synchronous httpx, fail-closed
on any transport failure (never an implicit APPROVED/READY), service token
obtained from Account Again (Conductor identifies as CONDUCTOR_MAIN — QA
Again verifies that token against Account Again's JWKS, it is never
trusted locally).
"""

import os
from typing import Any, Optional

import httpx

from app.integration.account_again_client import AccountAgainClient, AccountAgainUnavailableError
from app.integration.service_health import check_service_identity

# Canonical local topology (ECOSYSTEM-H1): PM Again owns :8000. QA Again's
# own default must never collide with it — :8002 is QA Again's canonical
# local port. Explicit QA_AGAIN_URL still takes precedence over this default.
QA_AGAIN_URL = os.getenv("QA_AGAIN_URL", "http://localhost:8002/api")
TIMEOUT_SECONDS = 5.0
EXPECTED_SERVICE = "QA_AGAIN"


class QAAgainUnavailableError(Exception):
    """Raised when QA Again cannot be reached or rejects the request.
    Callers must fail closed — never fabricate a QAResult on this path."""


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {AccountAgainClient.get_service_token()}"}


class QAAgainClient:
    """CONDUCTOR_MAIN's client for QA Again (independent QA execution/acceptance)."""

    @staticmethod
    def health() -> bool:
        """Healthy iff reachable AND the responder identifies itself as
        QA_AGAIN — HTTP 200 alone is not proof of service identity (a
        misconfigured/colliding service on the same port would also
        answer 200). Fails closed on any mismatch (ECOSYSTEM-H1)."""
        return check_service_identity(
            f"{QA_AGAIN_URL}/health", expected_service=EXPECTED_SERVICE, timeout=TIMEOUT_SECONDS,
        )

    @staticmethod
    def dispatch_qa_request(
        *, qa_request: dict[str, Any], idempotency_key: str, tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Sends a canonical QARequest to QA Again's intake endpoint.
        Raises QAAgainUnavailableError on transport failure or a non-2xx
        response — caller decides fallback policy, this client never
        silently swallows a failed dispatch.

        tenant_id, when given, is forwarded as X-Tenant-Id — the actual
        DeliveryRun's tenant, matching PMAgainClient's own convention."""
        try:
            headers = {**_auth_headers(), "Idempotency-Key": idempotency_key}
            if tenant_id:
                headers["X-Tenant-Id"] = tenant_id
            resp = httpx.post(
                f"{QA_AGAIN_URL}/ecosystem/qa-requests",
                json=qa_request, headers=headers, timeout=TIMEOUT_SECONDS,
            )
        except (httpx.HTTPError, AccountAgainUnavailableError) as e:
            raise QAAgainUnavailableError(f"QA Again unreachable: {e}") from e
        if resp.status_code == 409:
            raise QAAgainUnavailableError(f"QA Again rejected as an idempotency conflict: {resp.text}")
        if resp.status_code >= 400:
            raise QAAgainUnavailableError(f"QA Again dispatch failed: {resp.status_code} {resp.text}")
        return resp.json()

    @staticmethod
    def get_qa_result(qa_request_id: str) -> Optional[dict[str, Any]]:
        """Fetches the canonical QAResult for a qaRequestId. Returns None
        (not a fabricated/synthetic result) when QA Again has no mapping
        for this request yet, execution hasn't produced a result yet, or
        it can't be reached — matching the same "never fabricate"
        principle PMAgainClient.get_pm_status uses."""
        try:
            headers = _auth_headers()
            resp = httpx.get(
                f"{QA_AGAIN_URL}/ecosystem/qa-requests/{qa_request_id}/qa-result",
                headers=headers, timeout=TIMEOUT_SECONDS,
            )
        except (httpx.HTTPError, AccountAgainUnavailableError):
            return None
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            return None
        return resp.json()
