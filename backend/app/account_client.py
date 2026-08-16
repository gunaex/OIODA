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

import hashlib
import os
import threading
import time

import httpx

AUTH_MODE = os.environ.get("AUTH_MODE", "local")
ACCOUNT_AGAIN_URL = os.environ.get("ACCOUNT_AGAIN_URL", "").rstrip("/")
# Account Again serves its API under /api/v1 (its real, observed contract).
ACCOUNT_AGAIN_PREFIX = "/api/v1"

# Auth validation cache: bounded, short TTL, keyed by a SHA-256 fingerprint of
# the credential (never the raw token), tenant-aware. Only ALLOW decisions are
# cached; DENY is always re-evaluated live. A cache read failure never falls
# back to ALLOW — it simply falls through to live validation (fail closed).
AUTH_CACHE_TTL = float(os.environ.get("AUTH_CACHE_TTL", "60"))
AUTH_CACHE_MAX = int(os.environ.get("AUTH_CACHE_MAX", "1000"))

CAPABILITY = "document-again:design:write"
# Account Again's service-identity registry uses an uppercase, underscore-
# separated system-id vocabulary (VALID_SYSTEM_IDS). Document Again must
# present the same identifier so AA can verify its service token.
SERVICE_SYSTEM_ID = "DOCUMENT_AGAIN"


class AccountAgainError(Exception):
    """Raised when Account Again validation cannot succeed. Always fail closed."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


def _fingerprint(token: str, account_id: str, tenant_id: str | None) -> str:
    """SHA-256 of (token, account, tenant) — no raw credential is ever stored."""
    h = hashlib.sha256()
    h.update(token.encode("utf-8"))
    h.update(b"\x00")
    h.update((account_id or "").encode("utf-8"))
    h.update(b"\x00")
    h.update((tenant_id or "").encode("utf-8"))
    return h.hexdigest()


class ValidationCache:
    """Bounded TTL cache for successful (ALLOW) validations only."""

    def __init__(self, ttl: float = AUTH_CACHE_TTL, max_entries: int = AUTH_CACHE_MAX):
        self.ttl = ttl
        self.max_entries = max_entries
        self._data: dict[str, tuple[float, dict]] = {}
        self._lock = threading.Lock()

    def get(self, fingerprint: str) -> dict | None:
        try:
            with self._lock:
                item = self._data.get(fingerprint)
                if item is None:
                    return None
                expires_at, actor = item
                if expires_at < time.monotonic():
                    self._data.pop(fingerprint, None)
                    return None
                return actor
        except Exception:
            # Cache failure must never authorize; treat as a miss.
            return None

    def put(self, fingerprint: str, actor: dict) -> None:
        try:
            with self._lock:
                if len(self._data) >= self.max_entries and fingerprint not in self._data:
                    # Evict a few expired entries, then oldest-inserted if needed.
                    now = time.monotonic()
                    expired = [k for k, (exp, _) in self._data.items() if exp < now]
                    for k in expired:
                        self._data.pop(k, None)
                    while len(self._data) >= self.max_entries:
                        self._data.pop(next(iter(self._data)), None)
                self._data[fingerprint] = (time.monotonic() + self.ttl, actor)
        except Exception:
            pass  # a failed write is never fatal; next call just re-validates


class AccountAgainClient:
    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None):
        self.base_url = (base_url or ACCOUNT_AGAIN_URL).rstrip("/")
        self._transport = transport
        self._cache = ValidationCache()

    def _client(self) -> httpx.Client:
        kwargs = {"timeout": 5.0}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def validate_actor(self, token: str, account_id: str, tenant_id: str | None) -> dict:
        """Validate a caller against Account Again. Returns resolved actor.

        Fails closed: missing config, network error, non-ALLOW decision or a
        rejected token all raise AccountAgainError. Only successful ALLOW
        results are cached (bounded TTL, token-fingerprint key); DENY and
        outages are always re-checked live.
        """
        if not self.base_url:
            raise AccountAgainError("ACCOUNT_AGAIN_URL is not configured", 503)
        if not token:
            raise AccountAgainError("Bearer token required", 401)
        if not account_id:
            raise AccountAgainError("Account id required", 401)

        fp = _fingerprint(token, account_id, tenant_id)
        cached = self._cache.get(fp)
        if cached is not None:
            return cached

        actor = self._validate_live(token, account_id, tenant_id)
        self._cache.put(fp, actor)
        return actor

    def _validate_live(self, token: str, account_id: str, tenant_id: str | None) -> dict:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            with self._client() as client:
                resp = client.post(
                    f"{self.base_url}{ACCOUNT_AGAIN_PREFIX}/entitlements/evaluate",
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
                acct = client.get(f"{self.base_url}{ACCOUNT_AGAIN_PREFIX}/accounts/{account_id}", headers=headers).json()
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
