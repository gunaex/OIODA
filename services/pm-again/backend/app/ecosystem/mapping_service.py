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

import re

from sqlalchemy.orm import Session

from .. import models
from ..database import get_project_engine, open_project_session
from ..routers.projects import slugify, RESERVED_SLUGS
from ..contracts.models import DeliveryWorkPackage, WorkPackageState
from . import intake_service

_BUSINESS_INTENT_SOURCE_TYPE = "BUSINESS_INTENT"


class TenantMismatch(Exception):
    """Raised when a DeliveryWorkPackage's caller tenant doesn't match the
    tenant already recorded on the project its businessIntentId maps to
    (CROSS_TENANT_DELIVERY_WORK_PACKAGE_REJECTED)."""

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
            if project.tenant_id and tenant_id and project.tenant_id != tenant_id:
                raise TenantMismatch(
                    f"businessIntentId {business_intent_id!r} is owned by tenant {project.tenant_id!r}, "
                    f"not the caller's tenant {tenant_id!r}"
                )
            # P1 UX: the materialized project name tracks the authoritative
            # Document Again project name. The slug stays stable (it is the
            # per-project DB identity); only the human-facing name updates.
            if title and project.name != title:
                project.name = title
                master_db.commit()
            return project

    base_slug = slugify(title) or slugify(business_intent_id)
    slug = base_slug
    suffix = 1
    while slug in RESERVED_SLUGS or master_db.query(models.Project).filter(models.Project.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    project = models.Project(name=title, slug=slug, project_type="simple", tenant_id=tenant_id)
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


_TRACK_PREFIX_RE = re.compile(r"^(?:REQ-)?(T\d+)-")


def _track_key_from_code(code: str | None) -> str | None:
    """Derive a workstream key from a requirement running code (REQ-T1-004 -> T1).

    Returns None when the code has no track prefix, in which case the
    requirement is grouped under an explicit "Unscoped" workstream."""
    if not code:
        return None
    m = _TRACK_PREFIX_RE.match(code.strip())
    return m.group(1).upper() if m else None


def _workstream_name_for(track_key: str, workstreams: list[dict]) -> str:
    """Match a Document Again workstream (architecture track) to a track key.

    Workstreams arrive as [{semantic_id, name}, ...]; a workstream whose name
    starts with the track label ("Track 1") wins. Otherwise a bare label is
    used — never a fabricated scope title."""
    if track_key == "UNSCOPED":
        return "Unscoped"
    label = f"Track {track_key[1:]}"
    for ws in workstreams or []:
        name = (ws or {}).get("name") or ""
        if name.strip().lower().startswith(label.lower()):
            return name.strip()
    return label


def _materialize_execution_model(
    project_db: Session,
    dwp: DeliveryWorkPackage,
    refs: list[dict],
    workstreams: list[dict],
) -> list[int]:
    """Turn a confirmed design baseline's requirement refs into PM-native work.

    One Function per track (workstream) and one requirement-backed Task per
    requirement, linked to its Function. No owner/date/priority is invented:
    those stay NULL / unassigned until a human plan provides evidence."""
    if not refs:
        return []

    # Group refs by track key, preserving first-seen order.
    grouped: dict[str, list[dict]] = {}
    for r in refs:
        if not isinstance(r, dict):
            continue
        key = _track_key_from_code(r.get("code")) or "UNSCOPED"
        grouped.setdefault(key, []).append(r)

    task_ids: list[int] = []
    for track_key, track_refs in grouped.items():
        name = _workstream_name_for(track_key, workstreams)
        # Idempotent: reuse an existing workstream of the same name so a
        # re-delivered handoff never duplicates Functions.
        function = project_db.query(models.Function).filter(models.Function.name == name).first()
        if function is None:
            function = models.Function(
                name=name,
                description="Execution workstream materialized from a confirmed design baseline "
                f"(DeliveryWorkPackage {dwp.workPackageId}).",
                type="Functional",
                phase="UR",  # requirements originate from the UR
                status="Confirmed",  # the baseline it derives from is confirmed
                owner=None,
            )
            project_db.add(function)
            project_db.flush()  # get function.id

        for r in track_refs:
            code = (r.get("code") or "").strip()
            title = (r.get("title") or "").strip()
            task_title = f"{code} — {title}" if code and title else (title or code or "Requirement")
            # Idempotent: skip tasks that already exist for this requirement.
            existing_task = project_db.query(models.Task).filter(models.Task.title == task_title).first()
            if existing_task:
                continue
            task = models.Task(
                title=task_title,
                description=f"Requirement-backed execution item. Baseline {dwp.businessIntentId} · "
                f"correlation {dwp.correlationId}",
                phase="UR",
                status=_STATE_TO_TASK_STATUS.get(dwp.state, "Todo"),
                priority=None,  # not provided by the source — unassigned, not invented
                owner=None,
                due_date=None,
                linked_function_id=function.id,
            )
            project_db.add(task)
            project_db.flush()
            task_ids.append(task.id)

    project_db.commit()
    return task_ids


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

    # Structured requirement refs ride in engineeringContext.constraints
    # (free-form object per the canonical contract). When present we decompose
    # them into a meaningful execution model instead of a single flat seed task.
    constraints = {}
    if dwp.engineeringContext:
        constraints = dwp.engineeringContext.constraints or {}
    refs = constraints.get("requirementRefs") or []
    workstreams = constraints.get("workstreams") or []

    project_db = open_project_session(project.slug)
    try:
        task_ids = _materialize_execution_model(project_db, dwp, refs, workstreams)
        if not task_ids:
            # Fallback: no structured requirements — keep the historical seed task.
            task = models.Task(
                title=dwp.title,
                description=f"Conductor DeliveryWorkPackage {dwp.workPackageId} (correlation {dwp.correlationId})",
                status=_STATE_TO_TASK_STATUS.get(dwp.state, "Todo"),
                priority="High" if dwp.priority in ("HIGH", "CRITICAL") else "Med",
            )
            project_db.add(task)
            project_db.commit()
            project_db.refresh(task)
            task_ids = [task.id]
    finally:
        project_db.close()

    intake_service.attach_local_mapping(
        master_db,
        reference,
        project_id=project.id,
        local_object_type="task",
        local_object_id=str(task_ids[0]),
        status="MAPPED",
    )
    return reference, project, True
