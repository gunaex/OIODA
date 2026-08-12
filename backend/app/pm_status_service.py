"""Builds a canonical PMStatus from real PM Again project state. Never
fabricates a value: a field with no real source is omitted (left None),
matching the same design principle already stated by Conductor's PM
adapter stub (build_pm_status_placeholder — "never fabricate").

Field mapping (canonical PMStatus field <- PM Again source):

  pmStatusId          <- generated (uuid4) per call, this is a report, not a
                          stored entity
  correlationId        <- caller-supplied (from the originating
                          ExternalWorkReference / DeliveryWorkPackage), or a
                          fresh id for a project with no ecosystem origin
  workPackageId         <- caller-supplied (ExternalWorkReference.source_object_id),
                          or the project slug when there is no ecosystem origin
  projectId              <- Project.slug
  projectStatus           <- derived from Task.status distribution + open
                          blocking BoardItems (see _derive_project_status)
  milestone                <- nearest upcoming GanttItem with is_milestone=True
                          (same source as dashboard.py's upcoming_milestones)
  tasks[]                    <- Task rows: id/title/status/assignedTo(owner)
  blockers[]                   <- BoardItem rows (issue/incident) not in a
                          closed state
  dependencies[]                 <- UNKNOWN today: PM Again has no domain
                          concept of work-package-to-work-package dependency,
                          only ExternalWorkReference.correlation_id. Omitted
                          rather than fabricated.
  estimatedCompletion              <- UNKNOWN today: slippage.py flags
                          at-risk/overdue but does not compute a projected
                          completion date. Omitted rather than fabricated.
  evidence[]                        <- links back to this project's own
                          dashboard/slippage endpoints (real, inspectable
                          PM Again state, not copied specialist payloads)
  reportedAt                         <- now()
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import models
from .contracts.models import (
    PMStatus,
    PMStatusTask,
    PMStatusBlocker,
    PMStatusEvidence,
    ProjectStatus,
)

_OPEN_BLOCKER_TYPES = ("issue", "incident")
_CLOSED_BLOCKER_STATUSES = ("Resolved", "Closed", "Promoted")


def _derive_project_status(tasks: list[models.Task], open_blockers: list[models.BoardItem]) -> ProjectStatus:
    if open_blockers:
        return ProjectStatus.BLOCKED
    if not tasks:
        return ProjectStatus.NOT_STARTED
    if any(t.status == "Blocked" for t in tasks):
        return ProjectStatus.BLOCKED
    if all(t.status == "Done" for t in tasks):
        return ProjectStatus.COMPLETED
    if all(t.status == "Todo" for t in tasks):
        return ProjectStatus.NOT_STARTED
    return ProjectStatus.IN_PROGRESS


def build_pm_status(
    slug: str,
    db: Session,
    *,
    correlation_id: str | None = None,
    work_package_id: str | None = None,
) -> PMStatus:
    tasks = db.query(models.Task).all()
    board_items = db.query(models.BoardItem).filter(models.BoardItem.item_type.in_(_OPEN_BLOCKER_TYPES)).all()
    open_blockers = [b for b in board_items if b.status not in _CLOSED_BLOCKER_STATUSES]

    gantt_items = db.query(models.GanttItem).filter(models.GanttItem.is_milestone.is_(True)).all()
    upcoming = sorted((g for g in gantt_items if g.progress < 100), key=lambda g: g.end_date)
    milestone = upcoming[0].name if upcoming else None

    return PMStatus(
        pmStatusId=str(uuid.uuid4()),
        correlationId=correlation_id or str(uuid.uuid4()),
        workPackageId=work_package_id or slug,
        projectId=slug,
        projectStatus=_derive_project_status(tasks, open_blockers),
        milestone=milestone,
        tasks=[
            PMStatusTask(
                id=t.task_code or str(t.id),
                title=t.title,
                status=t.status,
                assignedTo=t.owner,
            )
            for t in tasks
        ],
        blockers=[
            PMStatusBlocker(
                id=b.item_code or str(b.id),
                description=b.title,
                severity=b.severity,
                status=b.status,
            )
            for b in open_blockers
        ],
        dependencies=None,
        estimatedCompletion=None,
        evidence=[
            PMStatusEvidence(
                type="project_dashboard",
                source="PM_AGAIN",
                reference=f"/api/{slug}/dashboard",
                summary="Real-time RAG health, overdue tasks, and open issues.",
            ),
            PMStatusEvidence(
                type="slippage_summary",
                source="PM_AGAIN",
                reference=f"/api/{slug}/slippage/summary",
                summary="Gantt-based and document-based schedule slippage signals.",
            ),
        ],
        reportedAt=datetime.now(timezone.utc),
    )
