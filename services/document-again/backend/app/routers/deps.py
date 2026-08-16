import os
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..account_client import AUTH_MODE, AccountAgainError, client
from ..db import get_db
from ..observability import metrics
from ..tenant import set_current_tenant

# Optional Account Again base URL for resolving display names (e.g. http://localhost:8001)
ACCOUNT_AGAIN_URL = os.environ.get("ACCOUNT_AGAIN_URL", "").rstrip("/")


async def tenant_scope(request: Request) -> None:
    """Global dependency: establish the request tenant scope and, in
    production auth mode, require a validated identity on every non-public
    route (including reads).

    In ``AUTH_MODE=local`` the tenant is taken from the ``X-Tenant-Id`` header
    (deterministic development tenancy). In ``AUTH_MODE=account_again`` every
    request except the explicitly public health/readiness/metrics endpoints
    must carry a valid Account Again service token + account id; otherwise it
    is rejected (fail closed) — no silent read bypass.

    Must be ``async``: a sync dependency would run in a threadpool context
    copy whose contextvar writes are invisible to the route handler.
    """
    if AUTH_MODE == "local":
        set_current_tenant(request.headers.get("X-Tenant-Id"))
        return

    # account_again: production read auth (P5-E)
    path = request.url.path
    if path in _PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi") or path.startswith("/redoc"):
        return
    token = (request.headers.get("Authorization") or "").strip()
    if token.startswith("Bearer "):
        token = token[len("Bearer "):].strip()
    account_id = request.headers.get("X-Account-Id") or request.headers.get("X-Subject-Id")
    try:
        info = await run_in_threadpool(client.validate_actor, token, account_id or "", request.headers.get("X-Tenant-Id"))
    except AccountAgainError as exc:
        metrics.inc("auth_denied")
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    set_current_tenant(info["tenant_id"])


_PUBLIC_PATHS = {"/api/health", "/api/readiness", "/api/metrics"}


@dataclass
class ActorContext:
    id: str
    name: str
    tenant_id: str | None = None
    source: str = "LOCAL"


async def actor(
    authorization: str | None = Header(default=None),
    x_actor: str | None = Header(default=None),
    x_account_id: str | None = Header(default=None),
    x_subject_id: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    x_actor_name: str | None = Header(default=None),
) -> str:
    """Actor display name, resolved per auth mode.

    - ``AUTH_MODE=account_again``: delegates to :func:`actor_ctx` so the
      caller is validated against Account Again. X-Actor is never trusted in
      production mode; a failed validation rejects the request.
    - ``AUTH_MODE=local``: deterministic development actor.
    """
    if AUTH_MODE == "account_again":
        ctx = await actor_ctx(
            authorization, x_actor, x_account_id, x_subject_id, x_tenant_id, x_actor_name
        )
        return ctx.name
    return x_actor or "local-user"


async def actor_ctx(
    authorization: str | None = Header(default=None),
    x_actor: str | None = Header(default=None),
    x_account_id: str | None = Header(default=None),
    x_subject_id: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    x_actor_name: str | None = Header(default=None),
) -> ActorContext:
    """Resolve the actor identity according to the configured auth mode.

    - ``AUTH_MODE=account_again``: a Bearer token + account/subject id are
      required and validated against Account Again. Any failure rejects the
      request — local identity is never silently substituted.
    - ``AUTH_MODE=local``: a deterministic development actor is used.
    """
    if AUTH_MODE not in ("local", "account_again"):
        raise HTTPException(status_code=503, detail="AUTH_MODE misconfigured")

    if AUTH_MODE == "account_again":
        token = (authorization or "").strip()
        if token.startswith("Bearer "):
            token = token[len("Bearer "):].strip()
        account_id = x_account_id or x_subject_id
        try:
            info = await run_in_threadpool(client.validate_actor, token, account_id or "", x_tenant_id)
        except AccountAgainError as exc:
            metrics.inc("auth_denied")
            raise HTTPException(status_code=exc.status_code, detail=str(exc))
        set_current_tenant(info["tenant_id"])
        return ActorContext(id=info["account_id"], name=info["display_name"], tenant_id=info["tenant_id"], source="ACCOUNT_AGAIN")

    # local development mode — deterministic, clearly separated
    account_id = x_account_id or x_subject_id
    if account_id:
        name = x_actor_name or x_actor or account_id
        set_current_tenant(x_tenant_id)
        return ActorContext(id=account_id, name=name, tenant_id=x_tenant_id, source="LOCAL")
    set_current_tenant(x_tenant_id)
    return ActorContext(id=f"local:{x_actor or 'local-user'}", name=x_actor or "local-user", tenant_id=x_tenant_id, source="LOCAL")


def db_session():
    yield from get_db()


__all__ = ["actor", "actor_ctx", "ActorContext", "db_session", "Session", "ACCOUNT_AGAIN_URL"]
