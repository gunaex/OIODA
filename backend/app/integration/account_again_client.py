"""
Conductor Again — Account Again Client (E8-C)

Sole HTTP boundary between Conductor Main and Account Again. No other module
should call Account Again's API directly. Fail-closed by design: any
transport failure is surfaced as an explicit DENY / unresolved result, never
treated as an implicit ALLOW (mirrors the LACC client's own philosophy).

Conductor identifies to Account Again as CONDUCTOR_MAIN using the
LOCAL_OIDC_COMPATIBLE_SERVICE_AUTH mechanism (E5.1): OAuth2-client-credentials
-shaped, RS256 JWT, 300s TTL, re-verified server-side on every call. The
`X-AGAIN-Service-Context` header is NEVER treated as authoritative here.
"""

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.integration.service_health import check_service_identity

ACCOUNT_AGAIN_URL = os.getenv("ACCOUNT_AGAIN_URL", "http://localhost:8001/api/v1")
SYSTEM_ID = os.getenv("ACCOUNT_AGAIN_SYSTEM_ID", "CONDUCTOR_MAIN")
CLIENT_SECRET = os.getenv("ACCOUNT_AGAIN_CLIENT_SECRET", "")
# Account Again is the trust authority and also auto-stops on Fly; give it a
# bounded 15s timeout so a cold trust call fails closed rather than timing out.
TIMEOUT_SECONDS = 15.0
EXPECTED_SERVICE = "account-again"


class AccountAgainUnavailableError(Exception):
    """Raised when Account Again cannot be reached. Callers must fail closed."""


class _TokenCache:
    """Caches the short-lived (300s) service token, refreshing before expiry."""

    def __init__(self):
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def get(self) -> str:
        with self._lock:
            if self._token and time.time() < self._expires_at - 15:  # 15s safety margin
                return self._token
            self._token = self._fetch()
            return self._token

    def _fetch(self) -> str:
        if not CLIENT_SECRET:
            raise AccountAgainUnavailableError(
                "ACCOUNT_AGAIN_CLIENT_SECRET not configured; cannot obtain a service token"
            )
        try:
            resp = httpx.post(
                f"{ACCOUNT_AGAIN_URL}/auth/service-token",
                json={"systemId": SYSTEM_ID, "clientSecret": CLIENT_SECRET},
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as e:
            raise AccountAgainUnavailableError(f"Account Again unreachable: {e}") from e
        if resp.status_code != 200:
            raise AccountAgainUnavailableError(
                f"Account Again denied service-token issuance: {resp.status_code} {resp.text}"
            )
        data = resp.json()
        self._expires_at = time.time() + data.get("expiresIn", 300)
        return data["accessToken"]

    def invalidate(self):
        with self._lock:
            self._token = None
            self._expires_at = 0.0


_token_cache = _TokenCache()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token_cache.get()}"}


class AccountAgainClient:
    """CONDUCTOR_MAIN's client for Account Again (identity/entitlement/credential authority)."""

    @staticmethod
    def is_configured() -> bool:
        return bool(CLIENT_SECRET)

    @staticmethod
    def health() -> bool:
        """Healthy iff reachable AND the responder identifies itself as
        account-again — HTTP 200 alone is not proof of service identity
        (ECOSYSTEM-H1)."""
        return check_service_identity(
            f"{ACCOUNT_AGAIN_URL}/health", expected_service=EXPECTED_SERVICE, timeout=TIMEOUT_SECONDS,
        )

    # ── Service auth (E5.1) ──────────────────────────────────

    @staticmethod
    def get_service_token() -> str:
        return _token_cache.get()

    # ── Entitlement evaluation ────────────────────────────────

    @staticmethod
    def evaluate_entitlement(
        *, tenant_id: Optional[str] = None, capability: Optional[str] = None,
        provider: Optional[str] = None, model: Optional[str] = None,
        product_id: Optional[str] = None, correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Real ALLOW/DENY decision from Account Again's entitlement engine.
        Fail-closed: any transport failure yields a synthetic DENY, never ALLOW."""
        body = {
            "tenantId": tenant_id,
            "serviceSystemId": SYSTEM_ID,
            "capability": capability,
            "provider": provider,
            "model": model,
            "productId": product_id,
            "correlationId": correlation_id,
            "idempotencyKey": idempotency_key,
        }
        try:
            headers = _auth_headers()
            resp = httpx.post(
                f"{ACCOUNT_AGAIN_URL}/entitlements/evaluate", json=body, headers=headers,
                timeout=TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, AccountAgainUnavailableError) as e:
            return {
                "entitlementDecisionId": "",
                "decision": "DENY",
                "reasonCode": "ACCOUNT_AGAIN_UNAVAILABLE",
                "reasonMessage": str(e),
                "evaluatedAt": _now_iso(),
            }

    # ── Credential resolution ─────────────────────────────────

    @staticmethod
    def resolve_credential(
        *, credential_ref: str, tenant_id: str, provider: str, purpose: str,
        correlation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Resolves a CredentialRef to a usable secret. Hard-required token (E5.1) —
        Conductor never stores or requests raw provider credentials of its own."""
        body = {
            "tenantId": tenant_id, "provider": provider, "purpose": purpose,
            "serviceSystemId": SYSTEM_ID, "correlationId": correlation_id,
        }
        try:
            headers = _auth_headers()
            resp = httpx.post(
                f"{ACCOUNT_AGAIN_URL}/credential-refs/{credential_ref}/resolve",
                json=body, headers=headers, timeout=TIMEOUT_SECONDS,
            )
            if resp.status_code == 401:
                _token_cache.invalidate()
                return {"resolved": False, "reason": "UNRESOLVABLE", "httpStatus": 401}
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, AccountAgainUnavailableError) as e:
            return {"resolved": False, "reason": "ACCOUNT_AGAIN_UNAVAILABLE", "error": str(e)}

    # ── Usage reporting ────────────────────────────────────────

    @staticmethod
    def report_usage(
        *, tenant_id: str, capability: Optional[str] = None, provider: Optional[str] = None,
        model: Optional[str] = None, total_tokens: Optional[int] = None,
        cost_cents: Optional[int] = None, correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        body = {
            "tenantId": tenant_id, "capability": capability, "provider": provider, "model": model,
            "totalTokens": total_tokens, "costCents": cost_cents,
            "correlationId": correlation_id, "idempotencyKey": idempotency_key,
            "serviceSystemId": SYSTEM_ID,
        }
        try:
            headers = _auth_headers()
            resp = httpx.post(f"{ACCOUNT_AGAIN_URL}/usage", json=body, headers=headers, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, AccountAgainUnavailableError) as e:
            return {"recorded": False, "error": str(e)}

    # ── Tenant / product entitlement lookups (for API middleware) ────

    @staticmethod
    def get_tenant(tenant_id: str) -> Optional[dict[str, Any]]:
        try:
            headers = _auth_headers()
            resp = httpx.get(f"{ACCOUNT_AGAIN_URL}/tenants/{tenant_id}", headers=headers, timeout=TIMEOUT_SECONDS)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            return None
