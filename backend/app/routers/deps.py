import os
from dataclasses import dataclass

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from ..account_client import AUTH_MODE, AccountAgainError, client
from ..db import get_db

# Optional Account Again base URL for resolving display names (e.g. http://localhost:8001)
ACCOUNT_AGAIN_URL = os.environ.get("ACCOUNT_AGAIN_URL", "").rstrip("/")


@dataclass
class ActorContext:
    id: str
    name: str
    tenant_id: str | None = None
    source: str = "LOCAL"


def actor(
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
        return actor_ctx(
            authorization, x_actor, x_account_id, x_subject_id, x_tenant_id, x_actor_name
        ).name
    return x_actor or "local-user"


def actor_ctx(
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
            info = client.validate_actor(token, account_id or "", x_tenant_id)
        except AccountAgainError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc))
        return ActorContext(id=info["account_id"], name=info["display_name"], tenant_id=info["tenant_id"], source="ACCOUNT_AGAIN")

    # local development mode — deterministic, clearly separated
    account_id = x_account_id or x_subject_id
    if account_id:
        name = x_actor_name or x_actor or account_id
        return ActorContext(id=account_id, name=name, tenant_id=x_tenant_id, source="LOCAL")
    return ActorContext(id=f"local:{x_actor or 'local-user'}", name=x_actor or "local-user", source="LOCAL")


def db_session():
    yield from get_db()


__all__ = ["actor", "actor_ctx", "ActorContext", "db_session", "Session", "ACCOUNT_AGAIN_URL"]
