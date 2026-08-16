"""OIDA Gateway / BFF (R16 Phase 6/13).

Routes the shell's /api/<service>/* prefixes to the bounded services over
private Fly networking. It is a thin correlation + SSO propagation layer — it
is NOT a business authority. It never holds or decides business logic, and it
never logs secrets, tokens or API keys.
"""
from __future__ import annotations

import os
import uuid

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OIDA Gateway", version="0.1.0")

# service prefix → (upstream base URL, upstream path prefix)
ROUTES = {
    "da": (os.environ.get("DOCUMENT_AGAIN_URL", "http://oida-document.internal:8003"), "/api"),
    "pm": (os.environ.get("PM_AGAIN_URL", "http://oida-pm.internal:8000"), "/api"),
    "qa": (os.environ.get("QA_AGAIN_URL", "http://oida-qa.internal:8002"), "/api"),
    "conductor": (os.environ.get("CONDUCTOR_AGAIN_URL", "http://oida-conductor.internal:8010"), "/api"),
    "account": (os.environ.get("ACCOUNT_AGAIN_URL", "http://oida-account.internal:8011"), "/api/v1"),
    "infra": (os.environ.get("INFRA_AGAIN_URL", "http://oida-infra.internal:18090"), "/api/v1"),
}

CORS_ORIGIN = os.environ.get("OIDA_WEB_ORIGIN", "https://oida.kanphong.com")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN, "http://localhost:5190"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "AVAILABLE", "service": "oida-gateway"}


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
    base, upstream_prefix = route
    target = f"{base}{upstream_prefix}/{path}"
    if request.url.query:
        target += f"?{request.url.query}"

    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length")}
    headers["x-request-id"] = headers.get("x-request-id") or uuid.uuid4().hex[:12]
    # Document Again (da) uses X-Actor for actor identity in local/ecosystem
    # mode; preserve the browser-provided actor if present.
    if service == "da" and "x-actor" not in {k.lower() for k in headers}:
        headers["x-actor"] = "local-user"

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
