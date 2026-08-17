"""OIDA Gateway / BFF.

Routes the shell's /api/<service>/* prefixes to the bounded services over
private Fly networking. It is a thin correlation + SSO propagation layer — it
is NOT a business authority. It never holds or decides business logic, and it
never logs secrets, tokens or API keys.

P0 authentication enforcement: DENY BY DEFAULT. Every browser-facing business
route requires a verified Account Again ecosystem identity token except an
explicit public allowlist (health, login, JWKS). User-supplied identity headers
(X-Actor, X-Account-Id, X-User, X-Role, X-Tenant-Id, …) are ALWAYS stripped;
a trusted actor context is re-derived from the verified token before forwarding
to the bounded services.
"""
from __future__ import annotations

import os
import threading
import time
import uuid

import httpx
import jwt
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OIDA Gateway", version="0.1.0")

# service prefix → (upstream base URL, upstream path prefix)
ROUTES = {
    "da": (os.environ.get("DOCUMENT_AGAIN_URL", "http://oida-document.internal:8003"), "/api"),
    "pm": (os.environ.get("PM_AGAIN_URL", "http://oida-pm.internal:8000"), "/api"),
    "qa": (os.environ.get("QA_AGAIN_URL", "http://oida-qa.internal:8000"), "/api"),
    "conductor": (os.environ.get("CONDUCTOR_AGAIN_URL", "http://oida-conductor.internal:8000"), "/api"),
    "account": (os.environ.get("ACCOUNT_AGAIN_URL", "http://oida-account.internal:8001"), "/api/v1"),
    "infra": (os.environ.get("INFRA_AGAIN_URL", "http://oida-infra.internal:8080"), "/api/v1"),
}

# ── Identity verification (Account Again human ecosystem tokens) ──────────
ACCOUNT_AGAIN_INTERNAL = os.environ.get(
    "ACCOUNT_AGAIN_INTERNAL_URL", "http://oida-account.internal:8001/api/v1"
)
IDENTITY_ISSUER = os.environ.get("ACCOUNT_AGAIN_ISSUER", "https://api-oida.kanphong.com")
IDENTITY_AUDIENCE = "again-ecosystem-identity"
_JWKS_TTL = 300.0

_jwks_state = {"keys": None, "ts": 0.0}
_jwks_lock = threading.Lock()

# Headers a client may never control. The gateway derives these itself from the
# verified token (or drops them entirely) — blocks X-Actor / X-User / X-Role /
# X-Tenant-Id spoofing against any bounded service.
_SPOOFABLE_HEADERS = {
    "x-actor", "x-actor-name", "x-account-id", "x-subject-id",
    "x-user", "x-role", "x-tenant-id", "x-user-id", "x-email",
}

# Public allowlist — everything else requires a verified identity (DENY BY
# DEFAULT). Preflight (OPTIONS) is always allowed so CORS can run.
PUBLIC_ROUTES = {
    ("account", "auth/ecosystem-token"),      # login / token issuance
    ("account", ".well-known/jwks.json"),     # public identity metadata
}


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    return None


def _verify_identity_token(token: str) -> dict:
    """Verify an RS256 Account Again human identity JWT. Raises on any
    failure (missing key, bad signature, wrong issuer/audience, expired)."""
    header = jwt.get_unverified_header(token)

    now = time.monotonic()
    with _jwks_lock:
        if _jwks_state["keys"] is None or (now - _jwks_state["ts"]) > _JWKS_TTL:
            resp = httpx.get(f"{ACCOUNT_AGAIN_INTERNAL}/.well-known/jwks.json", timeout=10.0)
            resp.raise_for_status()
            _jwks_state["keys"] = resp.json()
            _jwks_state["ts"] = now

    public_key = None
    for key in _jwks_state["keys"].get("keys", []):
        if key.get("kid") == header.get("kid"):
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            break
    if public_key is None:
        raise ValueError(f"No matching JWKS key for kid={header.get('kid')!r}")

    return jwt.decode(
        token,
        key=public_key,
        algorithms=["RS256"],
        audience=IDENTITY_AUDIENCE,
        issuer=IDENTITY_ISSUER,
    )


def _unauthorized(detail: str = "Not authenticated") -> Response:
    return Response(content='{"detail":"' + detail + '"}', status_code=401,
                    media_type="application/json")


CORS_ORIGIN = os.environ.get("OIDA_WEB_ORIGIN", "https://oida.kanphong.com")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN, "http://localhost:5190"],
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.pages\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "AVAILABLE", "service": "oida-gateway"}


@app.get("/api/auth/me")
def auth_me(request: Request):
    """Single identity-validation endpoint for the shell bootstrap. Requires a
    valid ecosystem token; returns the verified human identity."""
    token = _extract_bearer(request)
    if not token:
        return _unauthorized()
    try:
        claims = _verify_identity_token(token)
    except Exception:
        return _unauthorized("Invalid or expired token")
    return {
        "email": claims.get("email"),
        "account_id": claims.get("accountId"),
        "subject_id": claims.get("subjectId"),
        "tenant_id": claims.get("tenantId"),
        "roles": claims.get("ecosystemRoles") or [],
        "must_change_password": bool(claims.get("mustChangePassword")),
    }


@app.get("/api/versions")
def versions():
    return {
        "gateway": "0.1.0",
        "account_again": os.environ.get("ACCOUNT_VERSION", "unknown"),
        "document_again": os.environ.get("DOCUMENT_VERSION", "unknown"),
        "pm_again": os.environ.get("PM_VERSION", "unknown"),
        "qa_again": os.environ.get("QA_VERSION", "unknown"),
        "infra_again": os.environ.get("INFRA_VERSION", "unknown"),
        "conductor_again": os.environ.get("CONDUCTOR_VERSION", "unknown"),
    }


@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(service: str, path: str, request: Request):
    route = ROUTES.get(service)
    if route is None:
        return Response(content='{"detail":"unknown service"}', status_code=404,
                        media_type="application/json")

    # CORS preflight never carries a token and must be answered.
    is_preflight = request.method == "OPTIONS"

    # Authentication enforcement (DENY BY DEFAULT).
    claims = None
    if not is_preflight and (service, path) not in PUBLIC_ROUTES:
        token = _extract_bearer(request)
        if not token:
            return _unauthorized()
        try:
            claims = _verify_identity_token(token)
        except Exception:
            return _unauthorized("Invalid or expired token")

    base, upstream_prefix = route
    target = f"{base}{upstream_prefix}/{path}"
    if request.url.query:
        target += f"?{request.url.query}"

    # Build forwarded headers: always drop spoofable identity headers, then
    # re-derive a trusted actor context from the verified token.
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length") and k.lower() not in _SPOOFABLE_HEADERS
    }
    headers["x-request-id"] = headers.get("x-request-id") or uuid.uuid4().hex[:12]

    if claims is not None:
        email = claims.get("email") or ""
        account_id = claims.get("accountId") or ""
        tenant_id = claims.get("tenantId") or ""
        # Document Again (local/ecosystem actor) receives ONLY gateway-derived
        # identity — never the browser's claimed actor.
        headers["x-actor"] = email or "authenticated-user"
        if account_id:
            headers["x-account-id"] = account_id
            headers["x-subject-id"] = claims.get("subjectId") or account_id
        if tenant_id:
            headers["x-tenant-id"] = tenant_id
        # Preserve the verified token so bounded services can re-verify.
        headers["authorization"] = request.headers.get("Authorization", "")

    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            upstream = await client.request(
                request.method, target, headers=headers, content=body,
            )
    except httpx.ConnectError:
        return Response(content='{"detail":"service unavailable","service":"' + service + '"}',
                        status_code=502, media_type="application/json")
    except httpx.TimeoutException:
        return Response(content='{"detail":"service timeout","service":"' + service + '"}',
                        status_code=504, media_type="application/json")

    # Normalize service failure: never present an outage as an empty success.
    response = Response(content=upstream.content, status_code=upstream.status_code)
    for k, v in upstream.headers.items():
        if k.lower() in ("content-type", "content-encoding", "content-disposition"):
            response.headers[k] = v
    response.headers["x-request-id"] = headers["x-request-id"]
    return response
