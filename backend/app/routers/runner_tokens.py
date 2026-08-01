from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_master_db
from ..auth import issue_runner_token, require_admin

router = APIRouter(prefix="/api/runner-tokens", tags=["runner-tokens"])


@router.post("", response_model=schemas.RunnerTokenOut)
def create_runner_token(
    payload: schemas.RunnerTokenCreate,
    db: Session = Depends(get_master_db),
    _admin: models.User = Depends(require_admin),
):
    """Mints a runner token and returns the raw value once — it is never
    retrievable again (only its hash is stored, same discipline as
    refresh tokens)."""
    raw_token, record = issue_runner_token(db, payload.label)
    return schemas.RunnerTokenOut(id=record.id, label=record.label, token=raw_token)
