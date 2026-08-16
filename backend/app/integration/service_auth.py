"""
Conductor Main — inbound service auth (P5-A).

Verifies Account Again-issued RS256 service JWTs against Account Again's JWKS
and enforces that only the DOCUMENT_AGAIN service identity may submit design
handoffs. CONDUCTOR_MAIN remains the only identity permitted to dispatch into
PM Again / QA Again (that is enforced in PM/QA's own
require_conductor_service_identity — Conductor never shares its identity).
"""
from __future__ import annotations

import os
import threading
import time

import httpx
import jwt
from fastapi import HTTPException, Request

ACCOUNT_AGAIN_URL = os.environ.get("ACCOUNT_AGAIN_URL", "http://localhost:8001/api/v1")
EXPECTED_ISSUER = os.environ.get("ACCOUNT_AGAIN_ISSUER", "account-again-local")
EXPECTED_AUDIENCE = "again-ecosystem-services"
_JWKS_CACHE_TTL_SECONDS = 300

DOCUMENT_AGAIN_SYSTEM_ID = "DOCUMENT_AGAIN"


class ServiceAuthError(Exception):
    """Any failure verifying an inbound service token — callers fail closed."""


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
                raise ServiceAuthError(f"Account Again JWKS unreachable: {exc}") from exc
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
    """Verify an Account Again RS256 service JWT; return claims."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise ServiceAuthError(f"Malformed service token: {exc}") from exc
    public_key = _public_key_for(header.get("kid"))
    try:
        return jwt.decode(
            token, key=public_key, algorithms=["RS256"],
            audience=EXPECTED_AUDIENCE, issuer=EXPECTED_ISSUER,
        )
    except jwt.InvalidTokenError as exc:
        raise ServiceAuthError(f"Service token failed verification: {exc}") from exc


def _bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing service bearer token")
    return auth[len("Bearer "):]


def require_document_again_service_identity(request: Request) -> dict:
    """Fail-closed: only a valid DOCUMENT_AGAIN service token may submit
    design handoffs. Arbitrary header strings are never trusted."""
    token = _bearer(request)
    try:
        claims = verify_service_token(token)
    except ServiceAuthError as exc:
        raise HTTPException(status_code=403, detail=f"Invalid service token: {exc}") from exc
    system_id = claims.get("systemId")
    if system_id != DOCUMENT_AGAIN_SYSTEM_ID:
        raise HTTPException(
            status_code=403,
            detail=f"Service identity {system_id!r} is not permitted to submit design handoffs",
        )
    return claims
