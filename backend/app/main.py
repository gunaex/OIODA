import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .account_client import AUTH_MODE, ACCOUNT_AGAIN_URL
from .db import engine
from .observability import configure_logging, log, metrics, set_request_id, started_at
from .routers.api import router
from .routers.deps import tenant_scope
from .services import DomainError

configure_logging()

app = FastAPI(title="Document Again", version="0.1.0", dependencies=[Depends(tenant_scope)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    set_request_id(rid)
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 1)
    response.headers["X-Request-Id"] = rid
    log.info("request", extra={"method": request.method, "path": request.url.path,
                               "status": response.status_code, "duration_ms": duration_ms})
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


app.include_router(router)


@app.get("/api/health")
def health():
    """Liveness: the process is alive. Does not imply dependencies are ready."""
    return {"status": "ok", "service": "document-again"}


@app.get("/api/readiness")
def readiness():
    """Readiness: dependencies required for production mode are usable.

    - database: always required
    - Account Again connectivity: required only in AUTH_MODE=account_again
    PM/QA availability deliberately does NOT gate readiness — Document Again
    remains a usable design workspace while those are down (their delivery is
    durable + retried via the outbox).
    """
    checks = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"

    checks["authMode"] = AUTH_MODE
    if AUTH_MODE == "account_again":
        try:
            import httpx
            r = httpx.get(f"{ACCOUNT_AGAIN_URL}/api/v1/health", timeout=3.0)
            checks["accountAgain"] = "ok" if r.status_code == 200 else f"status {r.status_code}"
        except Exception as exc:  # noqa: BLE001
            checks["accountAgain"] = f"unreachable: {exc}"
            return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
    else:
        checks["accountAgain"] = "not required in local mode"

    ready = checks.get("database") == "ok"
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@app.get("/api/metrics")
def get_metrics():
    """In-process operational counters (no heavyweight monitoring infra)."""
    return {
        "uptime_seconds": round(time.monotonic() - started_at(), 1),
        "counters": metrics.snapshot(),
    }
