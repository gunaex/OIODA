from fastapi import Header
from sqlalchemy.orm import Session

from ..db import get_db


def actor(x_actor: str | None = Header(default=None)) -> str:
    return x_actor or "local-user"


def db_session():
    yield from get_db()


__all__ = ["actor", "db_session", "Session"]
