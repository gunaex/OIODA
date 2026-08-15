"""Account Again integration client — real trust validation, fail-closed.

Document Again never trusts arbitrary actor identity headers in production
mode. In ``AUTH_MODE=account_again`` every mutating request must carry an
Account Again service bearer token plus a subject/account id; Document Again
delegates token verification to Account Again's ``/entitlements/evaluate``
endpoint (which re-checks live service-identity status on every call) and
resolves display metadata from ``/accounts/{id}``.

In ``AUTH_MODE=local`` a deterministic development actor is used and the
integration is never silently substituted for real validation.
"""
from __future__ import annotations

import os

import httpx

AUTH_MODE = os.environ.get("AUTH_MODE", "local")
ACCOUNT_AGAIN_URL = os.environ.get("ACCOUNT_AGAIN_URL", "").rstrip("/")

CAPABILITY = "document-again:design:write"
SERVICE_SYSTEM_ID = "document-again"


class AccountAgainError(Exception):
    """Raised when Account Again validation cannot succeed. Always fail closed."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class AccountAgainClient:
    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        self.base_url = (base_url or ACCOUNT_AGAIN_URL).rstrip("/")
        self._transport = transport

    def _client(self) -> httpx.Client:
        kwargs = {"timeout": 5.0}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def validate_actor(self, token: str, account_id: str, tenant_id: str | None) -> dict:
        """Validate a caller against Account Again. Returns resolved actor.

        Fails closed: missing config, network error, non-ALLOW decision or a
        rejected token all raise AccountAgainError.
        """
        if not self.base_url:
            raise AccountAgainError("ACCOUNT_AGAIN_URL is not configured", 503)
        if not token:
            raise AccountAgainError("Bearer token required", 401)
        if not account_id:
            raise AccountAgainError("Account id required", 401)

        headers = {"Authorization": f"Bearer {token}"}
        try:
            with self._client() as client:
                resp = client.post(
                    f"{self.base_url}/entitlements/evaluate",
                    json={
                        "accountId": account_id,
                        "tenantId": tenant_id,
                        "serviceSystemId": SERVICE_SYSTEM_ID,
                        "capability": CAPABILITY,
                    },
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise AccountAgainError(f"Account Again unreachable: {exc}", 503) from exc

        if resp.status_code in (401, 403):
            raise AccountAgainError("Account Again rejected the token", resp.status_code)
        if resp.status_code != 200:
            raise AccountAgainError(f"Account Again error {resp.status_code}", 502)

        body = resp.json()
        decision = body.get("decision")
        if decision != "ALLOW":
            raise AccountAgainError(
                f"Entitlement decision is {decision or 'DENY'}",
                403,
            )

        display_name = account_id
        resolved_tenant = tenant_id
        try:
            with self._client() as client:
                acct = client.get(f"{self.base_url}/accounts/{account_id}", headers=headers).json()
            display_name = acct.get("displayName") or account_id
            resolved_tenant = acct.get("tenantId") or tenant_id
        except Exception:
            pass  # display metadata is best-effort; identity is already validated

        return {
            "account_id": account_id,
            "display_name": display_name,
            "tenant_id": resolved_tenant,
            "source": "ACCOUNT_AGAIN",
        }


client = AccountAgainClient()
