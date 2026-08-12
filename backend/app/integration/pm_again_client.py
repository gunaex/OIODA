"""
Conductor Again — PM Again Client (E8-E §43 / PM-E5)

HTTP boundary between Conductor Main and PM Again. Mirrors
account_again_client.py's shape and philosophy: synchronous httpx,
fail-closed on any transport failure (never an implicit ALLOW/READY),
service token obtained from Account Again (Conductor identifies as
CONDUCTOR_MAIN — PM Again verifies that token against Account Again's JWKS,
it is never trusted locally).
"""

import os
from typing import Any, Optional

import httpx

from app.integration.account_again_client import AccountAgainClient

PM_AGAIN_URL = os.getenv("PM_AGAIN_URL", "http://localhost:8000/api")
TIMEOUT_SECONDS = 5.0


class PMAgainUnavailableError(Exception):
    """Raised when PM Again cannot be reached or rejects the request.
    Callers must fail closed — never fabricate a result on this path."""


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {AccountAgainClient.get_service_token()}"}


class PMAgainClient:
    """CONDUCTOR_MAIN's client for PM Again (project execution visibility)."""

    @staticmethod
    def health() -> bool:
        try:
            resp = httpx.get(f"{PM_AGAIN_URL}/health", timeout=TIMEOUT_SECONDS)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    @staticmethod
    def dispatch_delivery_work_package(
        *, delivery_work_package: dict[str, Any], idempotency_key: str,
    ) -> dict[str, Any]:
        """Sends a canonical DeliveryWorkPackage to PM Again's intake
        endpoint. Raises PMAgainUnavailableError on transport failure or a
        non-2xx response — caller decides fallback policy, this client never
        silently swallows a failed dispatch."""
        try:
            headers = {**_auth_headers(), "Idempotency-Key": idempotency_key}
            resp = httpx.post(
                f"{PM_AGAIN_URL}/ecosystem/delivery-work-packages",
                json=delivery_work_package, headers=headers, timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as e:
            raise PMAgainUnavailableError(f"PM Again unreachable: {e}") from e
        if resp.status_code == 409:
            raise PMAgainUnavailableError(f"PM Again rejected as an idempotency conflict: {resp.text}")
        if resp.status_code >= 400:
            raise PMAgainUnavailableError(f"PM Again dispatch failed: {resp.status_code} {resp.text}")
        return resp.json()

    @staticmethod
    def get_pm_status(work_package_id: str) -> Optional[dict[str, Any]]:
        """Fetches the canonical PMStatus for a work package. Returns None
        (not a fabricated/synthetic status) when PM Again has no mapping for
        this work package yet, or when it can't be reached — matching the
        same "never fabricate" principle the adapter stub always had."""
        try:
            headers = _auth_headers()
            resp = httpx.get(
                f"{PM_AGAIN_URL}/ecosystem/pm-status",
                params={"workPackageId": work_package_id}, headers=headers, timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError:
            return None
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            return None
        return resp.json()
