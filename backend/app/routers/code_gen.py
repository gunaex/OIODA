"""The one standalone endpoint the Running Code Generator needs beyond what's
built into the tasks/functions create+import flows: the on-screen preview.

Everything else (auto-generate on save, pointer advance on manual override,
duplicate rejection) lives inside routers/tasks.py and routers/functions.py,
right next to the code that already handles creating those entities.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import code_generator, models
from ..auth import require_internal
from ..database import get_master_db, get_project_db

router = APIRouter(prefix="/api/{slug}", tags=["code-generator"], dependencies=[Depends(require_internal)])


@router.get("/next-code-preview")
def next_code_preview(
    slug: str,
    entity_type: str = Query(..., pattern="^(task|function)$"),
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    """Read-only: shows what the next code WOULD be, without burning it. Call
    it again after Regenerate — it never advances the sequence."""
    try:
        code = code_generator.peek_next_code(db, master_db, slug, entity_type)
    except code_generator.CodeGeneratorError as exc:
        raise code_generator.as_http_error(exc)
    return {"code": code}
