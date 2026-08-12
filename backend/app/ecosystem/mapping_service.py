"""Maps an inbound canonical QARequest onto QA Again's own domain
(QA-E4 §8-10).

Chosen mapping (mirrors PM Again's businessIntentId -> project link):

  QARequest.workPackageId -> one QA project (reused for every QARequest
                              under the same work package)
  QARequest                -> one TestCycle inside that project, snapshot
                              of the project's most recently PUBLISHED
                              revision (any suite)

QA Again stores only external ids / correlation / status / references here
— it does not duplicate Conductor's BusinessIntent/DeliveryRun state
(NO_CONDUCTOR_DOMAIN_DUPLICATION). It also never fabricates test content:
if the resolved project has no PUBLISHED revision yet, the QARequest is
recorded (RECEIVED) but left unmapped rather than inventing test cases —
see QAREQUEST_TO_EXISTING_QA_DOMAIN and the QA_RUNNER_LIMITATION-style
disclosure this mirrors.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .. import ecosystem_intake, models
from ..contracts.v1 import QARequest as CanonicalQARequest
from ..database import get_project_engine, open_project_session
from ..routers.projects import slugify, RESERVED_SLUGS


class TenantMismatch(Exception):
    """Raised when a QARequest's caller tenant doesn't match the tenant
    already recorded on the project its workPackageId maps to
    (CROSS_TENANT_QAREQUEST_BLOCKED)."""


def _find_or_create_project(master_db: Session, *, work_package_id: str, tenant_id: Optional[str]) -> models.Project:
    link = (
        master_db.query(models.ExternalQAProjectLink)
        .filter(models.ExternalQAProjectLink.work_package_id == work_package_id)
        .first()
    )
    if link:
        project = master_db.query(models.Project).filter(models.Project.id == link.project_id).first()
        if project:
            if project.tenant_id and tenant_id and project.tenant_id != tenant_id:
                raise TenantMismatch(
                    f"workPackageId {work_package_id!r} is owned by tenant {project.tenant_id!r}, "
                    f"not the caller's tenant {tenant_id!r}"
                )
            return project

    base_slug = slugify(f"wp-{work_package_id}")
    slug = base_slug
    suffix = 1
    while slug in RESERVED_SLUGS or master_db.query(models.Project).filter(models.Project.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    project = models.Project(name=f"Work Package {work_package_id}", slug=slug, tenant_id=tenant_id)
    master_db.add(project)
    master_db.commit()
    master_db.refresh(project)
    get_project_engine(slug)  # provisions the per-project SQLite DB

    master_db.add(
        models.ExternalQAProjectLink(work_package_id=work_package_id, project_id=project.id, tenant_id=tenant_id)
    )
    master_db.commit()
    return project


def _find_mappable_revision(project_db: Session) -> Optional[models.ScriptRevision]:
    """Most recently published revision (any suite) with at least one test
    case — the same real, human-authored content an ordinary TestCycle
    would be created from. Returns None if the project has nothing
    publishable yet; QA Again does not fabricate cases to fill the gap."""
    revisions = (
        project_db.query(models.ScriptRevision)
        .filter(models.ScriptRevision.status == "PUBLISHED")
        .order_by(models.ScriptRevision.published_at.desc())
        .all()
    )
    for revision in revisions:
        has_case = (
            project_db.query(models.TestCase.id)
            .filter(models.TestCase.revision_id == revision.id)
            .first()
        )
        if has_case:
            return revision
    return None


def _create_cycle_from_qa_request(project_db: Session, revision: models.ScriptRevision, qar: CanonicalQARequest) -> models.TestCycle:
    cases = project_db.query(models.TestCase).filter(models.TestCase.revision_id == revision.id).all()
    release_candidate = qar.releaseCandidate or {}
    cycle = models.TestCycle(
        suite_id=revision.suite_id,
        script_revision_id=revision.id,
        cycle_code=f"QAR-{qar.qaRequestId}",
        name=f"Ecosystem QARequest {qar.qaRequestId}",
        environment="ecosystem",
        release_version=release_candidate.get("commit") or release_candidate.get("tag"),
        target_base_url=None,
        status="READY",
        require_evidence_for_pass=True,
        created_by="ecosystem:CONDUCTOR_MAIN",
    )
    project_db.add(cycle)
    project_db.flush()
    for case in cases:
        project_db.add(models.CycleTestResult(cycle_id=cycle.id, test_case_id=case.id, status="NOT_RUN"))
    project_db.commit()
    project_db.refresh(cycle)
    return cycle


def intake_qa_request(
    master_db: Session,
    qar: CanonicalQARequest,
    *,
    idempotency_key: str,
    tenant_id: Optional[str] = None,
) -> tuple[models.ExternalQARequest, Optional[models.Project], bool]:
    """Returns (external_request, project, created). created=False means
    this exact QARequest payload was already ingested (idempotent replay)
    — no new project, cycle, or QAExecutionAttempt is created.

    project is None only if the workPackageId cannot be resolved to a
    project even after creating one, which should not normally happen —
    kept Optional defensively rather than asserted, matching the "never
    fabricate" discipline elsewhere in this module.
    """
    payload = qar.to_canonical_dict()

    external_request, created = ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key=idempotency_key,
        qa_request_id=qar.qaRequestId,
        correlation_id=qar.correlationId,
        source_system="CONDUCTOR_MAIN",
        payload=payload,
        tenant_id=tenant_id,
        engineering_result_ref=qar.engineeringResultReference,
        infrastructure_result_ref=qar.infrastructureResultReference,
    )

    if not created:
        project = None
        if external_request.qa_project_slug:
            project = master_db.query(models.Project).filter(models.Project.slug == external_request.qa_project_slug).first()
        return external_request, project, False

    project = _find_or_create_project(master_db, work_package_id=qar.workPackageId, tenant_id=tenant_id)

    project_db = open_project_session(project.slug)
    try:
        revision = _find_mappable_revision(project_db)
        if revision is None:
            # Honest limitation: nothing published to test against yet.
            # ExternalQARequest stays RECEIVED, unmapped, until either a
            # revision is published or an operator maps it manually.
            return external_request, project, True

        cycle = _create_cycle_from_qa_request(project_db, revision, qar)
    finally:
        project_db.close()

    ecosystem_intake.map_to_cycle(
        master_db, external_request, qa_project_slug=project.slug, cycle_id=cycle.id, triggered_by="ecosystem:CONDUCTOR_MAIN"
    )
    return external_request, project, True
