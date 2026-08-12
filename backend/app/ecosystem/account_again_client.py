"""PM Again's client to Account Again — identity/tenant/entitlement
authority. Mirrors the pattern used elsewhere in the AGAIN ecosystem
(Conductor's app/integration/account_again_client.py): synchronous httpx,
fail-closed on any transport/verification error (never implicit ALLOW),
short-lived caches rather than trusting a token forever."""

import os
import threading
import time

import httpx
import jwt

ACCOUNT_AGAIN_URL = os.environ.get("ACCOUNT_AGAIN_URL", "http://localhost:8001/api/v1")
_JWKS_CACHE_TTL_SECONDS = 300
_ENTITLEMENT_CACHE_TTL_SECONDS = 30

# Account Again's local dev service-auth issuer/audience — see
# ACCOUNT-AGAIN/account_again/services/service_auth.py.
EXPECTED_ISSUER = "account-again-local"
EXPECTED_AUDIENCE = "again-ecosystem-services"


def health() -> bool:
    try:
        resp = httpx.get(f"{ACCOUNT_AGAIN_URL}/health", timeout=3.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


class ServiceAuthError(Exception):
    """Raised for any failure verifying an inbound service token or
    evaluating entitlement — callers must treat this as a hard deny, never
    fall back to trusting the request anyway."""


class _JWKSCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._keys: dict | None = None
        self._fetched_at: float = 0.0

    def get(self) -> dict:
        with self._lock:
            if self._keys is not None and (time.monotonic() - self._fetched_at) < _JWKS_CACHE_TTL_SECONDS:
                return self._keys
            try:
                resp = httpx.get(f"{ACCOUNT_AGAIN_URL}/.well-known/jwks.json", timeout=5.0)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise ServiceAuthError(f"Account Again JWKS endpoint unreachable: {exc}") from exc
            self._keys = resp.json()
            self._fetched_at = time.monotonic()
            return self._keys


_jwks_cache = _JWKSCache()


def _public_key_for(kid: str | None):
    jwks = _jwks_cache.get()
    for key in jwks.get("keys", []):
        if kid is None or key.get("kid") == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)
    raise ServiceAuthError(f"No matching JWKS key for kid={kid!r}")


def verify_service_token(token: str) -> dict:
    """Verifies an RS256 service JWT issued by Account Again and returns its
    claims. Raises ServiceAuthError on any failure — expired, bad signature,
    wrong issuer/audience, or the JWKS endpoint itself being unreachable."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise ServiceAuthError(f"Malformed service token: {exc}") from exc

    public_key = _public_key_for(header.get("kid"))

    try:
        claims = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=EXPECTED_AUDIENCE,
            issuer=EXPECTED_ISSUER,
        )
    except jwt.InvalidTokenError as exc:
        raise ServiceAuthError(f"Service token failed verification: {exc}") from exc
    return claims


class _EntitlementCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._entries: dict[tuple, tuple[float, dict]] = {}

    def evaluate(self, *, tenant_id: str, product_id: str, service_system_id: str) -> dict:
        key = (tenant_id, product_id, service_system_id)
        with self._lock:
            cached = self._entries.get(key)
            if cached and (time.monotonic() - cached[0]) < _ENTITLEMENT_CACHE_TTL_SECONDS:
                return cached[1]
        try:
            resp = httpx.post(
                f"{ACCOUNT_AGAIN_URL}/entitlements/evaluate",
                json={"tenantId": tenant_id, "productId": product_id, "serviceSystemId": service_system_id},
                timeout=5.0,
            )
            resp.raise_for_status()
            decision = resp.json()
        except httpx.HTTPError as exc:
            # Fail-closed: any transport failure is an explicit DENY, never
            # an implicit ALLOW.
            decision = {"decision": "DENY", "reasonCode": "ACCOUNT_AGAIN_UNAVAILABLE", "reasonMessage": str(exc)}
        with self._lock:
            self._entries[key] = (time.monotonic(), decision)
        return decision


_entitlement_cache = _EntitlementCache()


def evaluate_entitlement(*, tenant_id: str, product_id: str = "PM_AGAIN", service_system_id: str = "PM_AGAIN") -> dict:
    """Returns Account Again's raw entitlement decision dict
    ({"decision": "ALLOW"|"DENY", "reasonCode": ..., ...}). Fail-closed on
    any transport failure."""
    return _entitlement_cache.evaluate(tenant_id=tenant_id, product_id=product_id, service_system_id=service_system_id)
