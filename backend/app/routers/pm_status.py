from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_master_db, get_project_db
from ..auth import get_current_user
from ..pm_status_service import build_pm_status
from ..contracts.validator import CanonicalContractValidator
from ..ecosystem.ecosystem_auth import require_project_tenant_match

# Baseline auth only — read-only, same visibility as the other
# Dashboard/Slippage endpoints (client_viewer included). Plus tenant match
# (no-op unless ECOSYSTEM_MODE=true and the project has a tenant_id set) —
# CROSS_TENANT_PMSTATUS_ACCESS_BLOCKED.
router = APIRouter(
    prefix="/api/{slug}/pm-status",
    tags=["pm-status"],
    dependencies=[Depends(get_current_user), Depends(require_project_tenant_match)],
)

_pmstatus_validator = CanonicalContractValidator("PMStatus")


@router.get("")
def project_pm_status(
    slug: str,
    correlation_id: str | None = None,
    work_package_id: str | None = None,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    status = build_pm_status(slug, db, correlation_id=correlation_id, work_package_id=work_package_id)
    payload = status.model_dump(mode="json", exclude_none=True)
    # PMSTATUS_CANONICAL_VALIDATION: never return a PMStatus that wouldn't
    # itself pass the canonical schema — this is the same validator used on
    # the intake side, so drift is caught symmetrically.
    _pmstatus_validator.validate(payload)
    return payload
