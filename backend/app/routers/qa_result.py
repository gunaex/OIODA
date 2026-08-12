"""QA-E3: canonical QAResult API.

GET /api/{slug}/cycles/{cycle_id}/qa-result returns the canonical
AGAIN-ECOSYSTEM QAResult for a cycle, built from QA Again's own runtime
state. Only available for cycles created via an ecosystem QARequest — see
app/qa_result_service.py.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..database import get_master_db, get_project_db
from ..qa_result_service import QAResultNotAvailableError, build_qa_result

router = APIRouter(prefix="/api/{slug}/cycles", tags=["qa-result"], dependencies=[Depends(get_current_user)])


@router.get("/{cycle_id}/qa-result")
def get_qa_result(
    slug: str,
    cycle_id: int,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    cycle = db.query(models.TestCycle).filter(models.TestCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    try:
        qa_result = build_qa_result(db, master_db, slug=slug, cycle_id=cycle_id)
    except QAResultNotAvailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return qa_result.to_canonical_dict()
