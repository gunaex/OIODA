from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_master_db
from ..auth import get_current_user
from ..ecosystem.ecosystem_auth import require_project_tenant_match

# Read-only: shows whether a project originated from an ecosystem source
# (e.g. Conductor Main) for the operator UI (PM-E7). None for a normal
# manually-created project — never fabricated.
router = APIRouter(
    prefix="/api/{slug}/ecosystem-source",
    tags=["ecosystem"],
    dependencies=[Depends(get_current_user), Depends(require_project_tenant_match)],
)


@router.get("")
def project_ecosystem_source(slug: str, master_db: Session = Depends(get_master_db)):
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        return None

    reference = (
        master_db.query(models.ExternalWorkReference)
        .filter(models.ExternalWorkReference.project_id == project.id)
        .order_by(models.ExternalWorkReference.created_at.asc())
        .first()
    )
    if not reference:
        return None

    return {
        "sourceSystem": reference.source_system,
        "sourceObjectType": reference.source_object_type,
        "sourceObjectId": reference.source_object_id,
        "correlationId": reference.correlation_id,
        "status": reference.status,
    }
