from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from .. import models
from ..database import get_master_db, get_project_db, open_project_session
from ..contracts.validator import CanonicalContractValidator, ValidationError as SchemaValidationError
from ..contracts.models import DeliveryWorkPackage
from ..ecosystem.service_auth import require_conductor_service_identity
from ..ecosystem.mapping_service import intake_delivery_work_package, TenantMismatch
from ..ecosystem.intake_service import IdempotencyConflict, raise_conflict_http
from ..pm_status_service import build_pm_status

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])

_dwp_validator = CanonicalContractValidator("DeliveryWorkPackage")
_pmstatus_validator = CanonicalContractValidator("PMStatus")


@router.post("/delivery-work-packages")
def intake_delivery_work_package_endpoint(
    request: Request,
    payload: dict,
    master_db: Session = Depends(get_master_db),
    claims: dict = Depends(require_conductor_service_identity),
):
    # Validate against the canonical schema first — a payload that doesn't
    # conform is rejected before it ever touches PM Again's own domain.
    try:
        _dwp_validator.validate(payload)
    except SchemaValidationError as exc:
        raise HTTPException(status_code=422, detail=f"DeliveryWorkPackage does not conform to canonical schema: {exc.message}")

    try:
        dwp = DeliveryWorkPackage.model_validate(payload)
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    idempotency_key = request.headers.get("Idempotency-Key") or f"CONDUCTOR_MAIN:DELIVERY_WORK_PACKAGE:{dwp.workPackageId}"
    tenant_id = claims.get("tenantId")

    try:
        reference, project, created = intake_delivery_work_package(
            master_db, dwp, idempotency_key=idempotency_key, tenant_id=tenant_id
        )
    except IdempotencyConflict as exc:
        raise raise_conflict_http(exc)
    except TenantMismatch as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return {
        "externalWorkReferenceId": reference.id,
        "correlationId": reference.correlation_id,
        "projectSlug": project.slug if project else None,
        "status": reference.status,
        "created": created,
    }


@router.get("/pm-status")
def pm_status_by_work_package(
    workPackageId: str,
    master_db: Session = Depends(get_master_db),
    claims: dict = Depends(require_conductor_service_identity),
):
    """Service-authenticated PMStatus lookup keyed by workPackageId — the
    identifier Conductor actually holds, unlike the human-facing
    /api/{slug}/pm-status endpoint which is keyed by project slug."""
    reference = (
        master_db.query(models.ExternalWorkReference)
        .filter(
            models.ExternalWorkReference.source_object_type == "DELIVERY_WORK_PACKAGE",
            models.ExternalWorkReference.source_object_id == workPackageId,
        )
        .first()
    )
    if not reference or not reference.project_id:
        raise HTTPException(status_code=404, detail="No PM Again project mapped for this workPackageId")

    project = master_db.query(models.Project).filter(models.Project.id == reference.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Mapped project no longer exists")

    project_db = open_project_session(project.slug)
    try:
        status = build_pm_status(
            project.slug, project_db, correlation_id=reference.correlation_id, work_package_id=workPackageId
        )
    finally:
        project_db.close()

    payload = status.model_dump(mode="json", exclude_none=True)
    _pmstatus_validator.validate(payload)
    return payload
