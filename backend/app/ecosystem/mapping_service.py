"""Maps an inbound canonical DeliveryWorkPackage onto PM Again's own domain.
Chosen mapping (documented per PM-E4 plan / master-prompt section 35):

  DeliveryWorkPackage.businessIntentId  -> one PM Project (reused across
                                            every work package under the
                                            same business intent)
  DeliveryWorkPackage                    -> one seed Task inside that
                                            project, per work package

PM Again stores only external id / title / correlation / status here — it
does not duplicate Conductor's orchestration engine state, full
BusinessIntent authority, or final readiness policy (NO_CONDUCTOR_DOMAIN_DUPLICATION)."""

from sqlalchemy.orm import Session

from .. import models
from ..database import get_project_engine, open_project_session
from ..routers.projects import slugify, RESERVED_SLUGS
from ..contracts.models import DeliveryWorkPackage, WorkPackageState
from . import intake_service

_BUSINESS_INTENT_SOURCE_TYPE = "BUSINESS_INTENT"
_WORK_PACKAGE_SOURCE_TYPE = "DELIVERY_WORK_PACKAGE"

_STATE_TO_TASK_STATUS = {
    WorkPackageState.DRAFT: "Todo",
    WorkPackageState.PLANNED: "Todo",
    WorkPackageState.IN_PROGRESS: "InProgress",
    WorkPackageState.WAITING_FOR_HUMAN: "InProgress",
    WorkPackageState.ENGINEERING_COMPLETE: "InProgress",
    WorkPackageState.INFRA_READY: "InProgress",
    WorkPackageState.QA_PENDING: "InProgress",
    WorkPackageState.QA_APPROVED: "InProgress",
    WorkPackageState.READY_FOR_DELIVERY: "InProgress",
    WorkPackageState.BLOCKED: "Blocked",
    WorkPackageState.NOT_READY: "Blocked",
    WorkPackageState.CANCELLED: "Done",
}


def _find_or_create_project(master_db: Session, *, business_intent_id: str, title: str, tenant_id: str | None) -> models.Project:
    business_intent_key = f"CONDUCTOR_MAIN:BUSINESS_INTENT:{business_intent_id}"
    existing_link = (
        master_db.query(models.ExternalWorkReference)
        .filter(models.ExternalWorkReference.idempotency_key == business_intent_key)
        .first()
    )
    if existing_link and existing_link.project_id:
        project = master_db.query(models.Project).filter(models.Project.id == existing_link.project_id).first()
        if project:
            return project

    base_slug = slugify(title) or slugify(business_intent_id)
    slug = base_slug
    suffix = 1
    while slug in RESERVED_SLUGS or master_db.query(models.Project).filter(models.Project.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    project = models.Project(name=title, slug=slug, project_type="simple")
    master_db.add(project)
    master_db.commit()
    master_db.refresh(project)
    get_project_engine(slug)  # provisions the per-project SQLite DB

    link, _ = intake_service.record_external_work(
        master_db,
        source_system="CONDUCTOR_MAIN",
        source_object_type=_BUSINESS_INTENT_SOURCE_TYPE,
        source_object_id=business_intent_id,
        correlation_id=business_intent_id,
        idempotency_key=business_intent_key,
        payload={"businessIntentId": business_intent_id},
        tenant_id=tenant_id,
    )
    intake_service.attach_local_mapping(
        master_db, link, project_id=project.id, local_object_type="project", local_object_id=str(project.id), status="MAPPED"
    )
    return project


def intake_delivery_work_package(
    master_db: Session,
    dwp: DeliveryWorkPackage,
    *,
    idempotency_key: str,
    tenant_id: str | None = None,
) -> tuple[models.ExternalWorkReference, models.Project, bool]:
    """Returns (reference, project, created). created=False means this exact
    work package payload was already ingested (idempotent replay) — no new
    project or task is created."""

    reference, created = intake_service.record_external_work(
        master_db,
        source_system="CONDUCTOR_MAIN",
        source_object_type=_WORK_PACKAGE_SOURCE_TYPE,
        source_object_id=dwp.workPackageId,
        correlation_id=dwp.correlationId,
        idempotency_key=idempotency_key,
        payload=dwp.model_dump(mode="json"),
        tenant_id=tenant_id,
    )

    if not created:
        project = master_db.query(models.Project).filter(models.Project.id == reference.project_id).first()
        return reference, project, False

    project = _find_or_create_project(
        master_db, business_intent_id=dwp.businessIntentId, title=dwp.title, tenant_id=tenant_id
    )

    project_db = open_project_session(project.slug)
    try:
        task = models.Task(
            title=dwp.title,
            description=f"Conductor DeliveryWorkPackage {dwp.workPackageId} (correlation {dwp.correlationId})",
            status=_STATE_TO_TASK_STATUS.get(dwp.state, "Todo"),
            priority="High" if dwp.priority in ("HIGH", "CRITICAL") else "Med",
        )
        project_db.add(task)
        project_db.commit()
        project_db.refresh(task)
        task_id = task.id
    finally:
        project_db.close()

    intake_service.attach_local_mapping(
        master_db,
        reference,
        project_id=project.id,
        local_object_type="task",
        local_object_id=str(task_id),
        status="MAPPED",
    )
    return reference, project, True
