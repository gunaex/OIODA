from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_master_db, get_project_db
from ..auth import get_current_user
from ..slippage import compute_task_slippage, compute_phase_slippage, compute_slippage_summary

# Baseline auth only — read-only, computed on the fly, same visibility as
# the other Dashboard endpoints (client_viewer included) per the spec's own
# RBAC instruction (item 6).
router = APIRouter(prefix="/api/{slug}/slippage", tags=["slippage"], dependencies=[Depends(get_current_user)])


def _get_project_or_404(slug: str, master_db: Session) -> models.Project:
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/tasks")
def slippage_tasks(slug: str, db: Session = Depends(get_project_db), master_db: Session = Depends(get_master_db)):
    _get_project_or_404(slug, master_db)
    return compute_task_slippage(db, master_db)


@router.get("/phases")
def slippage_phases(slug: str, db: Session = Depends(get_project_db), master_db: Session = Depends(get_master_db)):
    project = _get_project_or_404(slug, master_db)
    return compute_phase_slippage(project, db, master_db)


@router.get("/summary")
def slippage_summary(slug: str, db: Session = Depends(get_project_db), master_db: Session = Depends(get_master_db)):
    project = _get_project_or_404(slug, master_db)
    return compute_slippage_summary(project, db, master_db)
