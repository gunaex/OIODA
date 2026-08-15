import os
from dataclasses import dataclass

from fastapi import Header
from sqlalchemy.orm import Session

from ..db import get_db

# Optional Account Again base URL for resolving display names (e.g. http://localhost:8001)
ACCOUNT_AGAIN_URL = os.environ.get("ACCOUNT_AGAIN_URL", "").rstrip("/")


@dataclass
class ActorContext:
    id: str
    name: str
    tenant_id: str | None = None
    source: str = "LOCAL"


def actor(x_actor: str | None = Header(default=None)) -> str:
    """Legacy display-name actor (kept for local-dev ergonomics)."""
    return x_actor or "local-user"


def actor_ctx(
    x_actor: str | None = Header(default=None),
    x_account_id: str | None = Header(default=None),
    x_subject_id: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    x_actor_name: str | None = Header(default=None),
) -> ActorContext:
    """Resolve a stable actor identity from Account Again-compatible headers.

    X-Account-Id / X-Subject-Id is the stable identity; display name falls
    back to X-Actor-Name → X-Actor → the id. Without any identity header we
    degrade to a local actor so local development keeps working.
    """
    account_id = x_account_id or x_subject_id
    if account_id:
        name = x_actor_name or x_actor or account_id
        return ActorContext(id=account_id, name=name, tenant_id=x_tenant_id, source="ACCOUNT_AGAIN")
    return ActorContext(id=f"local:{x_actor or 'local-user'}", name=x_actor or "local-user", source="LOCAL")


def db_session():
    yield from get_db()


__all__ = ["actor", "actor_ctx", "ActorContext", "db_session", "Session", "ACCOUNT_AGAIN_URL"]
