from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_master_db, get_project_db
from ..auth import get_current_user
from ..dashboard import build_project_dashboard, build_global_dashboard

# Baseline auth only (no require_internal) — this is explicitly the landing
# page after login for every role per the spec, including client_viewer.
project_router = APIRouter(prefix="/api/{slug}/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])
global_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


@project_router.get("")
def project_dashboard(
    slug: str,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return build_project_dashboard(slug, db, master_db)


@global_router.get("/global")
def global_dashboard(master_db: Session = Depends(get_master_db)):
    return build_global_dashboard(master_db)
