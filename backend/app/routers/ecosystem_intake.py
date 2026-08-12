from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from ..database import get_master_db
from ..contracts.validator import CanonicalContractValidator, ValidationError as SchemaValidationError
from ..contracts.models import DeliveryWorkPackage
from ..ecosystem.service_auth import require_conductor_service_identity
from ..ecosystem.mapping_service import intake_delivery_work_package
from ..ecosystem.intake_service import IdempotencyConflict, raise_conflict_http

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])

_dwp_validator = CanonicalContractValidator("DeliveryWorkPackage")


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

    return {
        "externalWorkReferenceId": reference.id,
        "correlationId": reference.correlation_id,
        "projectSlug": project.slug if project else None,
        "status": reference.status,
        "created": created,
    }
