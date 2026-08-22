"""Thin HTTP routers. All rules live in app.services."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import services as svc
from ..tenant import current_tenant
from .deps import actor, actor_ctx, db_session

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Serialization helpers (explicit, no ORM leaking)
# ---------------------------------------------------------------------------


def project_out(p: m.Project) -> dict:
    return {
        "id": p.id, "key": p.key, "name": p.name, "description": p.description,
        "metadata": p.project_meta or {},
        "lifecycle_state": p.lifecycle_state or "ACTIVE",
        "cloned_from_project_id": p.cloned_from_project_id,
        "created_at": p.created_at.isoformat(), "created_by": p.created_by,
    }


def artifact_out(a: m.Artifact) -> dict:
    return {
        "id": a.id, "project_id": a.project_id, "type": a.type.value, "title": a.title,
        "current_draft_revision_id": a.current_draft_revision_id,
        "created_at": a.created_at.isoformat(), "created_by": a.created_by,
    }


def revision_out(r: m.ArtifactRevision, with_snapshot: bool = True) -> dict:
    out = {
        "id": r.id, "artifact_id": r.artifact_id, "revision_number": r.revision_number,
        "status": r.status.value, "based_on_revision_id": r.based_on_revision_id,
        "title": r.title, "created_at": r.created_at.isoformat(), "created_by": r.created_by,
        "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None,
        "confirmed_by": r.confirmed_by,
    }
    if with_snapshot:
        out["snapshot"] = r.snapshot
    return out


def baseline_out(b: m.Baseline) -> dict:
    return {
        "id": b.id, "project_id": b.project_id, "name": b.name,
        "description": b.description, "created_at": b.created_at.isoformat(),
        "created_by": b.created_by,
        "bindings": [
            {
                "artifact_id": bb.artifact_id,
                "artifact_revision_id": bb.artifact_revision_id,
                "semantic_object_id": bb.semantic_object_id,
                "semantic_object_type": bb.semantic_object_type,
            }
            for bb in b.bindings
        ],
    }


def requirement_out(r: m.Requirement) -> dict:
    return {
        "id": r.id, "project_id": r.project_id, "code": r.code, "title": r.title,
        "description": r.description, "source_type": r.source_type,
        "source_reference": r.source_reference, "status": r.status.value,
        "priority": r.priority, "created_at": r.created_at.isoformat(),
        "created_by": r.created_by, "metadata": r.metadata_json,
    }


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectIn(BaseModel):
    key: str
    name: str
    description: str | None = None
    metadata: dict | None = None


@router.get("/projects")
def list_projects(state: str | None = None, db: Session = Depends(db_session)):
    rows = svc.list_projects(db, state=state)
    return [project_out(p) for p in rows]


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, db: Session = Depends(db_session), actor=Depends(actor)):
    return project_out(svc.create_project(db, **body.model_dump(), actor=actor))


class ProjectArchiveIn(BaseModel):
    pass


class ProjectCopilotIn(BaseModel):
    query_type: str = "FOCUS_TODAY"
    question: str | None = None
    user_role: str | None = None
    force: bool = False


class BriefingReviewedIn(BaseModel):
    cutoff: str
    briefing_cursor: str
    evidence_cursors: list[str]


class PortfolioReviewedIn(BaseModel):
    portfolio_cursor: str
    project_cutoffs: dict
    project_evidence_cursors: dict
    included_project_ids: list[str]


@router.post("/projects/{project_id}/archive")
def archive_project(project_id: str, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.archive_project(db, project_id, actor=actx.name, actor_id=actx.id)


@router.post("/projects/{project_id}/restore")
def restore_project(project_id: str, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.restore_project(db, project_id, actor=actx.name, actor_id=actx.id)


class ProjectCloneIn(BaseModel):
    key: str
    name: str
    description: str | None = None


@router.post("/projects/{project_id}/clone", status_code=201)
def clone_project(project_id: str, body: ProjectCloneIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.clone_project(db, project_id, key=body.key, name=body.name,
                             description=body.description, actor=actx.name, actor_id=actx.id)


@router.get("/projects/{project_id}/delete-impact")
def delete_impact(project_id: str, db: Session = Depends(db_session)):
    return svc.delete_impact(db, project_id)


class ProjectDeleteIn(BaseModel):
    confirm_key: str


@router.post("/projects/{project_id}/delete")
def delete_project(project_id: str, body: ProjectDeleteIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    project = svc.guard_project(db, project_id)
    if body.confirm_key.strip().upper() != (project.key or "").upper():
        raise svc.DomainError("Confirmation key does not match the project key.", status_code=422)
    return svc.delete_project(db, project_id, actor=actx.name, actor_id=actx.id)


@router.get("/projects/{project_id}/export")
def export_project(project_id: str, db: Session = Depends(db_session)):
    return svc.export_project(db, project_id)


@router.post("/projects/import", status_code=201)
def import_project(body: dict, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.import_project(db, body, actor=actx.name, actor_id=actx.id)


# R16 Phase 29 — version surface (build identifiers recorded at the R16
# baseline repo checkpoint; monorepo release tags supersede these).
@router.get("/versions")
def versions():
    return {
        "oida_web": "oida-shell (R16 baseline; monorepo apps/oida-web)",
        "gateway": "oida-gateway (ops/fly/oida-gateway.fly.toml)",
        "account_again": {"version": "0.1.0", "baseline_commit": "ff535bd"},
        "document_again": {"version": "0.1.0", "baseline_commit": "1f98375"},
        "conductor_again": {"version": "0.1.0", "baseline_commit": "243942b"},
        "pm_again": {"version": "0.1.0", "baseline_commit": "fa3345d"},
        "qa_again": {"version": "0.1.0", "baseline_commit": "ea00066"},
        "infra_again": {"version": "0.1.0", "baseline_commit": "c389e58"},
        "note": "Commit identifiers are the R16 pre-consolidation repo HEADs; a monorepo release tag (e.g. oida-v0.1.0) is created only after production acceptance.",
    }


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(db_session)):
    return project_out(svc.guard_project(db, project_id))


@router.get("/projects/{project_id}/home")
def project_home(project_id: str, db: Session = Depends(db_session)):
    return svc.project_home(db, project_id)


# ---------------------------------------------------------------------------
# Workspace bindings (R12) — correlation metadata only, never business truth.
# ---------------------------------------------------------------------------

class WorkspaceBindingsIn(BaseModel):
    pm_project_slug: str | None = None
    qa_project_slugs: dict[str, str] | None = None  # handoff_id -> qa project slug
    infra_design_id: str | None = None  # Infra Again design id (correlation pointer)
    binding_contract: dict | None = None


@router.get("/projects/{project_id}/workspace-bindings")
def get_workspace_bindings(project_id: str, db: Session = Depends(db_session)):
    return svc.get_workspace_bindings(db, project_id)


@router.put("/projects/{project_id}/workspace-bindings")
def put_workspace_bindings(project_id: str, body: WorkspaceBindingsIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.put_workspace_bindings(db, project_id, pm_project_slug=body.pm_project_slug,
                                      qa_project_slugs=body.qa_project_slugs,
                                      infra_design_id=body.infra_design_id,
                                      binding_contract=body.binding_contract)


@router.get("/projects/{project_id}/truth")
def project_truth(project_id: str, db: Session = Depends(db_session),
                  authorization: str | None = Header(default=None)):
    from ..project_truth import build_project_truth
    return build_project_truth(svc.guard_project(db, project_id), authorization)


@router.get("/projects/{project_id}/command-center")
def project_command_center(project_id: str, authorization: str | None = Header(default=None),
                           db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    from ..command_center import compose
    from ..briefing import generate
    project = svc.guard_project(db, project_id)
    center = compose(db, project, authorization=authorization)
    center["daily_briefing"] = generate(db, project, user_id=actx.id, center=center)
    return center


@router.post("/projects/{project_id}/copilot")
def project_copilot(project_id: str, body: ProjectCopilotIn,
                    authorization: str | None = Header(default=None),
                    db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    from ..command_center import compose, copilot
    center = compose(db, svc.guard_project(db, project_id), authorization=authorization)
    return copilot(center, query_type=body.query_type, question=body.question,
                   user_role=body.user_role, force=body.force)


@router.get("/projects/{project_id}/resolution-intelligence")
def project_resolution_intelligence(project_id: str,
                                    authorization: str | None = Header(default=None),
                                    db: Session = Depends(db_session)):
    from ..command_center import compose
    center = compose(db, svc.guard_project(db, project_id), authorization=authorization)
    return center["resolution_intelligence"]


@router.post("/projects/{project_id}/resolution-intelligence/assistant")
def project_resolution_intelligence_assistant(
        project_id: str, authorization: str | None = Header(default=None),
        db: Session = Depends(db_session)):
    from ..command_center import compose
    from ..resolution_intelligence import assistant
    center = compose(db, svc.guard_project(db, project_id), authorization=authorization)
    return assistant(center["resolution_intelligence"])


@router.get("/projects/{project_id}/briefing")
def project_briefing(project_id: str, authorization: str | None = Header(default=None),
                     db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    from ..briefing import generate
    return generate(db, svc.guard_project(db, project_id), user_id=actx.id, authorization=authorization)


@router.post("/projects/{project_id}/briefing/mark-reviewed")
def mark_project_briefing_reviewed(project_id: str, body: BriefingReviewedIn,
                                   db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    from ..briefing import acknowledge
    project = svc.guard_project(db, project_id)
    return acknowledge(db, project, user_id=actx.id, cutoff=body.cutoff,
        briefing_cursor=body.briefing_cursor, evidence_cursors=body.evidence_cursors,
        actor_id=actx.id)


@router.post("/projects/{project_id}/briefing/ai")
def project_briefing_ai(project_id: str, authorization: str | None = Header(default=None),
                        db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    from ..briefing import ai_explain, generate
    packet = generate(db, svc.guard_project(db, project_id), user_id=actx.id, authorization=authorization)
    return ai_explain(packet)


@router.get("/portfolio/command-center")
def portfolio_command_center(authorization: str | None = Header(default=None),
                             db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    from ..portfolio import compose
    return compose(db, user_id=actx.id, authorization=authorization)


@router.post("/portfolio/mark-reviewed")
def mark_portfolio_reviewed(body: PortfolioReviewedIn, db: Session = Depends(db_session),
                            actx=Depends(actor_ctx)):
    from ..portfolio import acknowledge
    return acknowledge(db, actx.id, body.model_dump(), actx.id)


@router.post("/portfolio/copilot")
def portfolio_copilot(body: ProjectCopilotIn, authorization: str | None = Header(default=None),
                      db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    from ..portfolio import compose, copilot
    return copilot(compose(db, user_id=actx.id, authorization=authorization), body.query_type)


# ---------------------------------------------------------------------------
# OIDA Suggestion (R11) — AI observes & suggests; the human decides.
# ---------------------------------------------------------------------------

class SuggestGenerateIn(BaseModel):
    mode: str = "STANDARD"  # QUICK | STANDARD | DEEP


@router.post("/projects/{project_id}/suggestions/generate")
def generate_suggestions(project_id: str, body: SuggestGenerateIn | None = None, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.generate_suggestions(db, project_id, mode=(body or SuggestGenerateIn()).mode, actor=actx.name, actor_id=actx.id)


@router.get("/projects/{project_id}/suggestions")
def list_suggestions(project_id: str, db: Session = Depends(db_session)):
    return svc.list_suggestions(db, project_id)


class SuggestAnswerIn(BaseModel):
    answer: str
    source: str = "CUSTOMER"


@router.post("/suggestions/{suggestion_id}/answer")
def answer_suggestion(suggestion_id: str, body: SuggestAnswerIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.answer_suggestion(db, suggestion_id, answer=body.answer, source=body.source, actor=actx.name, actor_id=actx.id)


@router.post("/suggestions/{suggestion_id}/interpret")
def interpret_suggestion(suggestion_id: str, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.interpret_suggestion(db, suggestion_id, actor=actx.name, actor_id=actx.id)


class SuggestReviewIn(BaseModel):
    decision: str  # ACCEPTED | REJECTED


@router.post("/suggestions/{suggestion_id}/review")
def review_suggestion(suggestion_id: str, body: SuggestReviewIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.review_suggestion(db, suggestion_id, decision=body.decision, actor=actx.name, actor_id=actx.id)


# ---------------------------------------------------------------------------
# AI providers (R11 extension) — honest, no keys stored server-side.
# ---------------------------------------------------------------------------

@router.get("/ai/providers")
def ai_providers():
    from .. import ai as ai_runtime
    return ai_runtime.provider_status()


@router.post("/ai/providers/{provider_id}/test")
def ai_provider_test(provider_id: str):
    from .. import ai as ai_runtime
    try:
        return ai_runtime.test_provider(provider_id)
    except KeyError:
        raise DomainError("Unknown provider", status_code=404)


class AIProviderSettingsIn(BaseModel):
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None


@router.get("/ai/providers/{provider_id}/settings")
def ai_provider_settings(provider_id: str):
    from .. import ai as ai_runtime
    try:
        return ai_runtime.get_provider_settings(provider_id)
    except KeyError:
        raise DomainError("Unknown provider", status_code=404)


@router.put("/ai/providers/{provider_id}/settings")
def update_ai_provider_settings(provider_id: str, body: AIProviderSettingsIn, actx=Depends(actor_ctx)):
    from .. import ai as ai_runtime
    try:
        return ai_runtime.update_provider_settings(
            provider_id, api_key=body.api_key, model=body.model, base_url=body.base_url
        )
    except KeyError:
        raise DomainError("Unknown provider", status_code=404)


@router.get("/ai/providers/{provider_id}/models")
def ai_provider_models(provider_id: str, x_provider_api_key: str | None = Header(None, alias="X-Provider-API-Key")):
    """Model list read live from the provider source — never hard-coded. An
    unsaved key typed in the UI may be passed via X-Provider-API-Key so the
    list can be fetched before saving."""
    from .. import ai as ai_runtime
    try:
        return ai_runtime.list_provider_models(provider_id, api_key=x_provider_api_key)
    except KeyError:
        raise DomainError("Unknown provider", status_code=404)


# ---------------------------------------------------------------------------
# R15 — Multi-Agent Council (AI-Ready, Human-Led)
# ---------------------------------------------------------------------------

@router.get("/ai/capabilities")
def ai_capabilities():
    from .. import council
    return council.capability_registry()


@router.get("/ai/council/mode")
def ai_council_mode():
    from .. import council
    return council.council_mode()


class CouncilConsultIn(BaseModel):
    task_type: str = "GENERAL_REVIEW"
    question: str
    context_envelope: dict = {}
    role: str | None = None


@router.post("/projects/{project_id}/council/consult")
def council_consult(project_id: str, body: CouncilConsultIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.create_consultation(
        db, project_id, task_type=body.task_type, question=body.question,
        context_envelope=body.context_envelope, role=body.role,
        actor=actx.name, actor_id=actx.id,
    )


@router.get("/projects/{project_id}/council/consultations")
def council_consultations(project_id: str, db: Session = Depends(db_session)):
    return svc.list_consultations(db, project_id)


@router.get("/projects/{project_id}/council/consultations/{consultation_id}")
def council_consultation(project_id: str, consultation_id: str, db: Session = Depends(db_session)):
    return svc.get_consultation(db, consultation_id)


class CouncilStaleIn(BaseModel):
    context_envelope: dict = {}


@router.post("/council/consultations/{consultation_id}/check-stale")
def council_check_stale(consultation_id: str, body: CouncilStaleIn, db: Session = Depends(db_session)):
    return svc.check_consultation_stale(db, consultation_id, context_envelope=body.context_envelope or None)


class CouncilReviewIn(BaseModel):
    decision: str  # USEFUL | REJECTED
    comment: str | None = None
    important: list[str] = []
    incorrect: list[str] = []


@router.post("/council/consultations/{consultation_id}/review")
def council_review(consultation_id: str, body: CouncilReviewIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.review_consultation(
        db, consultation_id, decision=body.decision, comment=body.comment,
        important=body.important, incorrect=body.incorrect,
        actor=actx.name, actor_id=actx.id,
    )


class CouncilToSuggestionIn(BaseModel):
    finding: dict


@router.post("/council/consultations/{consultation_id}/to-suggestion")
def council_to_suggestion(consultation_id: str, body: CouncilToSuggestionIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.council_finding_to_suggestion(
        db, consultation_id, finding=body.finding, actor=actx.name, actor_id=actx.id,
    )


class CouncilRerunIn(BaseModel):
    context_envelope: dict


@router.post("/council/consultations/{consultation_id}/rerun")
def council_rerun(consultation_id: str, body: CouncilRerunIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.rerun_consultation(
        db, consultation_id, context_envelope=body.context_envelope,
        actor=actx.name, actor_id=actx.id,
    )


# ---------------------------------------------------------------------------
# Artifacts + revisions
# ---------------------------------------------------------------------------


class ArtifactIn(BaseModel):
    project_id: str
    type: m.ArtifactType
    title: str
    snapshot: dict | None = None


@router.get("/projects/{project_id}/artifacts")
def list_artifacts(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Artifact).where(m.Artifact.project_id == project_id)
    ).scalars()
    return [artifact_out(a) for a in rows]


@router.post("/artifacts", status_code=201)
def create_artifact(body: ArtifactIn, db: Session = Depends(db_session), actor=Depends(actor)):
    a = svc.create_artifact(db, **body.model_dump(), actor=actor)
    return {**artifact_out(a), "revisions": [revision_out(r) for r in a.revisions]}


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, db: Session = Depends(db_session)):
    a = svc.get_or_404(db, m.Artifact, artifact_id, "Artifact")
    return {**artifact_out(a), "revisions": [revision_out(r, with_snapshot=False) for r in a.revisions]}


class RevisionIn(BaseModel):
    snapshot: dict | None = None
    based_on_revision_id: str | None = None
    title: str | None = None


@router.post("/artifacts/{artifact_id}/revisions", status_code=201)
def create_revision(
    artifact_id: str, body: RevisionIn, db: Session = Depends(db_session), actor=Depends(actor)
):
    rev = svc.create_revision(
        db,
        artifact_id=artifact_id,
        snapshot=body.snapshot,
        based_on_revision_id=body.based_on_revision_id,
        actor=actor,
    )
    return revision_out(rev)


@router.get("/revisions/{revision_id}")
def get_revision(revision_id: str, db: Session = Depends(db_session)):
    return revision_out(svc.get_or_404(db, m.ArtifactRevision, revision_id, "Revision"))


class SnapshotIn(BaseModel):
    snapshot: dict
    title: str | None = None


@router.put("/revisions/{revision_id}/snapshot")
def update_snapshot(revision_id: str, body: SnapshotIn, db: Session = Depends(db_session)):
    return revision_out(
        svc.update_revision_snapshot(db, revision_id, body.snapshot, body.title)
    )


@router.post("/revisions/{revision_id}/submit-for-review")
def submit_for_review(revision_id: str, db: Session = Depends(db_session)):
    return revision_out(svc.submit_for_review(db, revision_id))


@router.post("/revisions/{revision_id}/return-to-draft")
def return_to_draft(revision_id: str, db: Session = Depends(db_session)):
    return revision_out(svc.transition_revision(db, revision_id, m.RevisionStatus.DRAFT))


class ConfirmIn(BaseModel):
    comment: str | None = None
    evidence: dict | None = None


@router.post("/revisions/{revision_id}/confirm")
def confirm(
    revision_id: str, body: ConfirmIn | None = None, db: Session = Depends(db_session),
    actor=Depends(actor), actx=Depends(actor_ctx),
):
    body = body or ConfirmIn()
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    rev, confirmation = svc.confirm_revision(
        db, revision_id, actor=actx.name, comment=body.comment, evidence=body.evidence, actor_id=actx.id
    )
    return {
        "revision": revision_out(rev),
        "confirmation": {
            "id": confirmation.id, "confirmed_by": confirmation.confirmed_by,
            "confirmed_at": confirmation.confirmed_at.isoformat(),
            "comment": confirmation.comment, "evidence": confirmation.evidence,
        },
    }


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


class BaselineIn(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    artifact_revision_ids: list[str]


@router.get("/projects/{project_id}/baselines")
def list_baselines(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Baseline).where(m.Baseline.project_id == project_id)
    ).scalars()
    return [baseline_out(b) for b in rows]


@router.post("/baselines", status_code=201)
def create_baseline(body: BaselineIn, db: Session = Depends(db_session), actor=Depends(actor), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return baseline_out(svc.create_baseline(db, **body.model_dump(), actor=actx.name, actor_id=actx.id))


@router.get("/baselines/{baseline_id}")
def get_baseline(baseline_id: str, db: Session = Depends(db_session)):
    return baseline_out(svc.resolve_baseline(db, baseline_id))


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


class RequirementIn(BaseModel):
    project_id: str
    title: str
    description: str | None = None
    source_type: str | None = None
    source_reference: str | None = None
    priority: str | None = None
    code: str | None = None
    metadata: dict | None = None


@router.get("/projects/{project_id}/requirements")
def list_requirements(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Requirement)
        .where(m.Requirement.project_id == project_id)
        .order_by(m.Requirement.code)
    ).scalars()
    return [requirement_out(r) for r in rows]


@router.post("/requirements", status_code=201)
def create_requirement(body: RequirementIn, db: Session = Depends(db_session), actor=Depends(actor)):
    return requirement_out(svc.create_requirement(db, **body.model_dump(), actor=actor))


@router.get("/requirements/{requirement_id}")
def get_requirement(requirement_id: str, db: Session = Depends(db_session)):
    return requirement_out(svc.get_or_404(db, m.Requirement, requirement_id, "Requirement"))


# ---------------------------------------------------------------------------
# Requirement revisions + change lifecycle (R10)
# ---------------------------------------------------------------------------


@router.get("/requirements/{requirement_id}/revisions")
def list_requirement_revisions(requirement_id: str, db: Session = Depends(db_session)):
    return [svc._requirement_revision_dict(r) for r in svc.list_requirement_revisions(db, requirement_id)]


@router.post("/requirements/{requirement_id}/draft", status_code=201)
def create_requirement_draft(requirement_id: str, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    change, draft = svc.create_requirement_draft(
        db, requirement_id, actor=actx.name, actor_id=actx.id,
    )
    return {"change_id": change.id, "draft": svc._requirement_revision_dict(draft)}


class RequirementDraftIn(BaseModel):
    title: str | None = None
    description: str | None = None
    source_type: str | None = None
    source_reference: str | None = None
    priority: str | None = None


@router.put("/requirements/{requirement_id}/draft/{revision_id}")
def update_requirement_draft(
    requirement_id: str, revision_id: str, body: RequirementDraftIn,
    db: Session = Depends(db_session),
):
    return svc._requirement_revision_dict(
        svc.update_requirement_draft(db, requirement_id, revision_id, **body.model_dump())
    )


@router.get("/projects/{project_id}/changes")
def list_requirement_changes(project_id: str, db: Session = Depends(db_session)):
    return svc.list_requirement_changes(db, project_id)


@router.get("/changes/{change_id}")
def get_requirement_change(change_id: str, db: Session = Depends(db_session)):
    rows = svc.list_requirement_changes(db)
    for row in rows:
        if row["id"] == change_id:
            return row
    svc.get_or_404(db, m.RequirementChange, change_id, "Change")  # raises 404
    return {}


@router.get("/changes/{change_id}/impact")
def change_impact(change_id: str, db: Session = Depends(db_session)):
    return svc.requirement_change_impact(db, change_id)


class RegenerateIn(BaseModel):
    mode: str = "affected"  # affected | full


@router.post("/changes/{change_id}/regenerate")
def regenerate_change(change_id: str, body: RegenerateIn | None = None, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    body = body or RegenerateIn()
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.regenerate_change(db, change_id, mode=body.mode, actor=actx.name, actor_id=actx.id)


class ConfirmChangeIn(BaseModel):
    confirmation_token: str


@router.post("/changes/{change_id}/confirm")
def confirm_change(change_id: str, body: ConfirmChangeIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.confirm_change(
        db, change_id, confirmation_token=body.confirmation_token,
        actor=actx.name, actor_id=actx.id,
    )


@router.post("/projects/{project_id}/seed-requirement-revisions")
def seed_requirement_revisions(project_id: str, db: Session = Depends(db_session)):
    return {"seeded": svc.seed_requirement_revisions(db, project_id)}


# ---------------------------------------------------------------------------
# Semantic objects + traces
# ---------------------------------------------------------------------------


class SemanticObjectIn(BaseModel):
    project_id: str
    semantic_id: str
    object_type: m.SemanticObjectType
    display_name: str
    entity_ref: str | None = None


@router.get("/projects/{project_id}/semantic-objects")
def list_semantic_objects(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.SemanticObject).where(m.SemanticObject.project_id == project_id)
    ).scalars()
    return [
        {
            "id": o.id, "semantic_id": o.semantic_id, "object_type": o.object_type.value,
            "display_name": o.display_name, "entity_ref": o.entity_ref,
        }
        for o in rows
    ]


@router.post("/semantic-objects", status_code=201)
def ensure_semantic(body: SemanticObjectIn, db: Session = Depends(db_session)):
    o = svc.ensure_semantic_object(
        db,
        project_id=body.project_id,
        semantic_id=body.semantic_id,
        object_type=body.object_type,
        display_name=body.display_name,
        entity_ref=body.entity_ref,
    )
    return {
        "id": o.id, "semantic_id": o.semantic_id, "object_type": o.object_type.value,
        "display_name": o.display_name, "entity_ref": o.entity_ref,
    }


class TraceIn(BaseModel):
    project_id: str
    source_semantic_id: str
    target_semantic_id: str
    relation_type: m.TraceRelationType
    revision_context: str | None = None


@router.get("/projects/{project_id}/traces")
def list_traces(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.TraceLink).where(m.TraceLink.project_id == project_id)
    ).scalars()
    return [
        {
            "id": t.id, "source": t.source_semantic_id, "target": t.target_semantic_id,
            "relation": t.relation_type.value, "revision_context": t.revision_context,
        }
        for t in rows
    ]


@router.post("/traces", status_code=201)
def create_trace(body: TraceIn, db: Session = Depends(db_session), actor=Depends(actor)):
    t = svc.create_trace_link(db, **body.model_dump(), actor=actor)
    return {"id": t.id, "source": t.source_semantic_id, "target": t.target_semantic_id,
            "relation": t.relation_type.value}


@router.get("/projects/{project_id}/impact/{semantic_id}")
def impact(project_id: str, semantic_id: str, db: Session = Depends(db_session)):
    return svc.impact_of(db, project_id, semantic_id)


@router.get("/projects/{project_id}/impact-analysis/{semantic_id}")
def impact_analysis(
    project_id: str, semantic_id: str, depth: int = 3, db: Session = Depends(db_session)
):
    return svc.impact_analysis(db, project_id, semantic_id, max_depth=min(max(depth, 1), 5))


@router.get("/projects/{project_id}/impact-v2/{semantic_id}")
def impact_analysis_v2(
    project_id: str, semantic_id: str, depth: int = 4, db: Session = Depends(db_session)
):
    return svc.impact_analysis_v2(db, project_id, semantic_id, max_depth=min(max(depth, 1), 6))


class ChangeSetIn(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    items: list[dict] | None = None


@router.post("/change-sets")
def create_change_set(body: ChangeSetIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.create_change_set(db, **body.model_dump(), actor=actx.name, actor_id=actx.id)


@router.get("/projects/{project_id}/change-sets")
def list_change_sets(project_id: str, db: Session = Depends(db_session)):
    return svc.list_change_sets(db, project_id=project_id)


@router.get("/projects/{project_id}/trace-graph")
def trace_graph(project_id: str, db: Session = Depends(db_session)):
    return svc.trace_graph(db, project_id)


@router.get("/projects/{project_id}/semantic-context/{semantic_id}")
def semantic_context(project_id: str, semantic_id: str, db: Session = Depends(db_session)):
    return svc.semantic_context(db, project_id, semantic_id)


@router.get("/projects/{project_id}/search")
def search(project_id: str, q: str = "", db: Session = Depends(db_session)):
    return svc.search_semantic(db, project_id, q)


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


class AnnotationIn(BaseModel):
    project_id: str
    anchor_object_type: str
    anchor_semantic_id: str
    content: str
    type: m.AnnotationType = m.AnnotationType.COMMENT
    artifact_revision_id: str | None = None
    canvas_x: float | None = None
    canvas_y: float | None = None
    drawing_payload: dict | None = None
    thread_id: str | None = None


def annotation_out(a: m.Annotation) -> dict:
    return {
        "id": a.id, "project_id": a.project_id, "artifact_revision_id": a.artifact_revision_id,
        "anchor_object_type": a.anchor_object_type, "anchor_semantic_id": a.anchor_semantic_id,
        "canvas_x": a.canvas_x, "canvas_y": a.canvas_y, "type": a.type.value,
        "content": a.content, "status": a.status.value, "created_by": a.created_by,
        "created_at": a.created_at.isoformat(),
    }


@router.get("/projects/{project_id}/annotations")
def list_annotations(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Annotation).where(m.Annotation.project_id == project_id)
    ).scalars()
    return [annotation_out(a) for a in rows]


@router.post("/annotations", status_code=201)
def create_annotation(body: AnnotationIn, db: Session = Depends(db_session), actor=Depends(actor), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return annotation_out(svc.create_annotation(db, **body.model_dump(), actor=actx.name, actor_id=actx.id))


@router.post("/annotations/{annotation_id}/status/{status}")
def set_status(annotation_id: str, status: m.AnnotationStatus, db: Session = Depends(db_session)):
    return annotation_out(svc.set_annotation_status(db, annotation_id, status))


# ---------------------------------------------------------------------------
# Review workflow (threads, summary, timeline)
# ---------------------------------------------------------------------------


class ThreadIn(BaseModel):
    project_id: str
    title: str | None = None


@router.get("/projects/{project_id}/threads")
def list_threads(project_id: str, db: Session = Depends(db_session)):
    return svc.list_threads(db, project_id)


@router.post("/threads", status_code=201)
def create_thread(body: ThreadIn, db: Session = Depends(db_session), actor=Depends(actor)):
    t = svc.create_thread(db, project_id=body.project_id, title=body.title, actor=actor)
    return {"id": t.id, "title": t.title, "resolved": t.resolved}


@router.get("/projects/{project_id}/annotations-summary")
def annotations_summary(project_id: str, db: Session = Depends(db_session)):
    return svc.annotations_summary(db, project_id)


@router.get("/projects/{project_id}/timeline")
def timeline(project_id: str, semantic_id: str | None = None, db: Session = Depends(db_session)):
    return svc.timeline(db, project_id, semantic_id=semantic_id)


@router.get("/revisions/{revision_id}/annotations")
def revision_annotations(revision_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Annotation).where(m.Annotation.artifact_revision_id == revision_id)
    ).scalars()
    return [annotation_out(a) for a in rows]


# ---------------------------------------------------------------------------
# Change requests
# ---------------------------------------------------------------------------


class CRIn(BaseModel):
    project_id: str
    requested_change: str
    affected_semantic_ids: list[str] = []
    title: str | None = None
    reason: str | None = None
    requested_by: str | None = None
    requested_date: str | None = None
    source_reference: str | None = None
    notes: str | None = None
    target_release: str | None = None
    schedule_impact: str | None = None
    commercial_impact: str | None = None
    classification: str | None = None


class CRSuggestIn(BaseModel):
    project_id: str
    affected_semantic_ids: list[str] = []


def cr_out(cr: m.ChangeRequest) -> dict:
    return {
        "id": cr.id, "code": cr.code, "project_id": cr.project_id,
        "title": cr.title,
        "requested_change": cr.requested_change, "reason": cr.reason,
        "requested_by": cr.requested_by,
        "requested_date": cr.requested_date.isoformat() if cr.requested_date else None,
        "source_reference": cr.source_reference, "notes": cr.notes,
        "status": cr.status.value, "target_release": cr.target_release,
        "schedule_impact": cr.schedule_impact, "commercial_impact": cr.commercial_impact,
        "affected_semantic_ids": [l.semantic_id for l in cr.links],
        "created_at": cr.created_at.isoformat(), "created_by": cr.created_by,
        "updated_at": cr.updated_at.isoformat() if cr.updated_at else None,
    }


def _cr_list_item(db: Session, cr: m.ChangeRequest) -> dict:
    item = cr_out(cr)
    impact = db.execute(
        select(m.ChangeRequestImpact).where(m.ChangeRequestImpact.change_request_id == cr.id)
    ).scalar_one_or_none()
    analysis = db.execute(
        select(m.ImpactAnalysis)
        .where(m.ImpactAnalysis.target_id == cr.id, m.ImpactAnalysis.target_type == "change_request")
        .order_by(m.ImpactAnalysis.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    item.update({
        "classification": impact.classification if impact else None,
        "impact_confidence": analysis.confidence if analysis else None,
        "human_review": analysis.review_state.value if analysis else "NOT_REVIEWED",
        "coverage_status": analysis.coverage_status if analysis else None,
        "effort_status": (impact.effort_impact or {}).get("status") if impact and impact.effort_impact else None,
        "commercial_status": impact.commercial_status if impact else None,
    })
    return item


@router.get("/projects/{project_id}/change-requests")
def list_crs(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.ChangeRequest).where(m.ChangeRequest.project_id == project_id)
    ).scalars()
    return [_cr_list_item(db, c) for c in rows]


@router.post("/change-requests", status_code=201)
def create_cr(body: CRIn, db: Session = Depends(db_session), actor=Depends(actor), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return cr_out(svc.create_change_request(db, **body.model_dump(), actor=actx.name, actor_id=actx.id))


@router.post("/change-requests/suggest-classification")
def suggest_cr_classification(body: CRSuggestIn, db: Session = Depends(db_session)):
    return svc.suggest_cr_classification(db, body.project_id, body.affected_semantic_ids)


@router.post("/change-requests/{change_request_id}/analyze-impact")
def analyze_cr_impact(
    change_request_id: str, db: Session = Depends(db_session), actx=Depends(actor_ctx),
):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.analyze_cr_impact(db, change_request_id, actor=actx.name, actor_id=actx.id)


@router.get("/change-requests/{change_request_id}/impact-analysis")
def get_cr_impact_analysis(change_request_id: str, db: Session = Depends(db_session)):
    return svc.get_cr_impact_analysis(db, change_request_id)


class CRReviewIn(BaseModel):
    analysis_id: str
    decisions: dict[str, dict] | None = None
    human_added: list[dict] | None = None
    comments: list[str] | None = None
    finalize: bool = False


@router.post("/change-requests/{change_request_id}/impact-analysis/review")
def review_cr_impact_analysis(
    change_request_id: str, body: CRReviewIn, db: Session = Depends(db_session), actx=Depends(actor_ctx),
):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.review_cr_impact_analysis(
        db, change_request_id, body.analysis_id,
        decisions=body.decisions, human_added=body.human_added,
        comments=body.comments, finalize=body.finalize,
        reviewer=actx.name, actor_id=actx.id,
    )


@router.get("/change-requests/{change_request_id}")
def get_cr(change_request_id: str, db: Session = Depends(db_session)):
    return svc.change_request_detail(db, change_request_id)


class CRImplementIn(BaseModel):
    artifact_revision_map: dict[str, dict] | None = None


@router.post("/change-requests/{change_request_id}/implement")
def implement_cr(
    change_request_id: str, body: CRImplementIn | None, db: Session = Depends(db_session),
    actor=Depends(actor),
):
    result = svc.implement_change_request(
        db, change_request_id, artifact_revision_map=(body or CRImplementIn()).artifact_revision_map,
        actor=actor,
    )
    return {"change_request": cr_out(result["change_request"]),
            "spawned_revisions": result["spawned_revisions"]}


@router.get("/change-requests/{change_request_id}/impact")
def get_cr_impact(change_request_id: str, db: Session = Depends(db_session)):
    return svc.cr_impact(db, change_request_id)


class CRImpactIn(BaseModel):
    classification: str | None = None
    function_impact: dict | None = None
    effort_impact: dict | None = None
    timeline_impact: dict | None = None
    technical_impact: dict | None = None
    qa_impact: dict | None = None
    infra_impact: dict | None = None
    commercial_status: str | None = None
    pricing_basis: str | None = None
    confidence: str | None = None


@router.put("/change-requests/{change_request_id}/impact")
def save_cr_impact(change_request_id: str, body: CRImpactIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.save_cr_impact(db, change_request_id, **body.model_dump())


class CRCustomerApprovalIn(BaseModel):
    decision: str  # APPROVED | REJECTED | PENDING
    approved_by: str | None = None
    reference: str | None = None
    note: str | None = None
    amount: str | None = None


@router.post("/change-requests/{change_request_id}/customer-approval")
def set_cr_customer_approval(change_request_id: str, body: CRCustomerApprovalIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.set_cr_customer_approval(db, change_request_id, **body.model_dump(), actor=actx.name)


class CRTransitionIn(BaseModel):
    to_status: str
    note: str | None = None


@router.post("/change-requests/{change_request_id}/transition")
def transition_cr(change_request_id: str, body: CRTransitionIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.transition_change_request(
        db, change_request_id, to_status=body.to_status, note=body.note,
        actor=actx.name, actor_id=actx.id,
    )


# ---------------------------------------------------------------------------
# Database design
# ---------------------------------------------------------------------------


class SchemaIn(BaseModel):
    project_id: str
    name: str
    semantic_id: str
    description: str | None = None


class TableIn(BaseModel):
    schema_id: str
    name: str
    semantic_id: str | None = None
    description: str | None = None


class FieldIn(BaseModel):
    table_id: str
    name: str
    data_type: str
    semantic_id: str | None = None
    length: int | None = None
    nullable: bool = False
    default: str | None = None
    primary_key: bool = False
    foreign_key: bool = False
    reference: str | None = None
    description: str | None = None
    remark: str | None = None


class RelationIn(BaseModel):
    schema_id: str
    from_field_semantic_id: str
    to_field_semantic_id: str
    relation_type: str = "MANY_TO_ONE"


@router.get("/projects/{project_id}/db-schemas")
def list_schemas(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.DatabaseSchema).where(m.DatabaseSchema.project_id == project_id)
    ).scalars()
    out = []
    for s in rows:
        out.append({
            "id": s.id, "semantic_id": s.semantic_id, "name": s.name,
            "description": s.description,
            "layout": s.layout or {},
            "tables": [
                {
                    "id": t.id, "semantic_id": t.semantic_id, "name": t.name,
                    "description": t.description,
                    "fields": [
                        {
                            "id": f.id, "semantic_id": f.semantic_id, "name": f.name,
                            "data_type": f.data_type, "length": f.length,
                            "nullable": f.nullable, "default": f.default,
                            "primary_key": f.primary_key, "foreign_key": f.foreign_key,
                            "reference": f.reference, "description": f.description,
                            "remark": f.remark,
                        }
                        for f in t.fields
                    ],
                }
                for t in s.tables
            ],
            "relations": [
                {
                    "id": r.id, "semantic_id": r.semantic_id,
                    "from": r.from_field_semantic_id, "to": r.to_field_semantic_id,
                    "relation_type": r.relation_type,
                }
                for r in db.execute(
                    select(m.DatabaseRelation).where(m.DatabaseRelation.schema_id == s.id)
                ).scalars()
            ],
        })
    return out


@router.post("/db-schemas", status_code=201)
def create_schema(body: SchemaIn, db: Session = Depends(db_session), actor=Depends(actor)):
    s = svc.create_schema(db, **body.model_dump(), actor=actor)
    return {"id": s.id, "semantic_id": s.semantic_id, "name": s.name}


@router.post("/db-tables", status_code=201)
def create_table(body: TableIn, db: Session = Depends(db_session)):
    t = svc.create_table(db, **body.model_dump())
    return {"id": t.id, "semantic_id": t.semantic_id, "name": t.name}


@router.post("/db-fields", status_code=201)
def create_field(body: FieldIn, db: Session = Depends(db_session)):
    f = svc.create_field(db, **body.model_dump())
    return {"id": f.id, "semantic_id": f.semantic_id, "name": f.name}


@router.post("/db-relations", status_code=201)
def create_relation(body: RelationIn, db: Session = Depends(db_session)):
    r = svc.create_relation(db, **body.model_dump())
    return {"id": r.id, "semantic_id": r.semantic_id}


# --- DB designer CRUD ---


class TablePatch(BaseModel):
    name: str


class FieldPatch(BaseModel):
    name: str | None = None
    data_type: str | None = None
    length: int | None = None
    nullable: bool | None = None
    default: str | None = None
    primary_key: bool | None = None
    foreign_key: bool | None = None
    reference: str | None = None
    description: str | None = None
    remark: str | None = None


class LayoutIn(BaseModel):
    layout: dict


def field_out(f: m.DatabaseField) -> dict:
    return {
        "id": f.id, "semantic_id": f.semantic_id, "name": f.name,
        "data_type": f.data_type, "length": f.length, "nullable": f.nullable,
        "default": f.default, "primary_key": f.primary_key, "foreign_key": f.foreign_key,
        "reference": f.reference, "description": f.description, "remark": f.remark,
    }


@router.patch("/db-tables/{table_id}")
def rename_table(table_id: str, body: TablePatch, db: Session = Depends(db_session)):
    t = svc.rename_table(db, table_id, body.name)
    return {"id": t.id, "semantic_id": t.semantic_id, "name": t.name}


@router.delete("/db-tables/{table_id}", status_code=204)
def delete_table(table_id: str, db: Session = Depends(db_session)):
    svc.delete_table(db, table_id)


@router.patch("/db-fields/{field_id}")
def update_field(field_id: str, body: FieldPatch, db: Session = Depends(db_session)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    f = svc.update_field(db, field_id, **changes)
    return field_out(f)


@router.delete("/db-fields/{field_id}", status_code=204)
def delete_field(field_id: str, db: Session = Depends(db_session)):
    svc.delete_field(db, field_id)


@router.delete("/db-relations/{relation_id}", status_code=204)
def delete_relation(relation_id: str, db: Session = Depends(db_session)):
    svc.delete_relation(db, relation_id)


@router.get("/db-schemas/{schema_id}/erd-layout")
def get_erd_layout(schema_id: str, db: Session = Depends(db_session)):
    return svc.get_erd_layout(db, schema_id)


@router.put("/db-schemas/{schema_id}/erd-layout")
def save_erd_layout(schema_id: str, body: LayoutIn, db: Session = Depends(db_session)):
    svc.save_erd_layout(db, schema_id, body.layout)
    return {"ok": True}


@router.get("/db-schemas/{schema_id}/design-snapshot")
def design_snapshot(schema_id: str, db: Session = Depends(db_session)):
    return svc.db_design_snapshot(db, schema_id)


# ---------------------------------------------------------------------------
# Process flow designer
# ---------------------------------------------------------------------------


class FlowIn(BaseModel):
    project_id: str
    name: str
    semantic_id: str
    description: str | None = None


class FlowStepIn(BaseModel):
    flow_id: str
    name: str
    step_type: str = "ACTION"
    semantic_id: str | None = None
    description: str | None = None


class FlowTransitionIn(BaseModel):
    flow_id: str
    from_step_semantic_id: str
    to_step_semantic_id: str
    label: str | None = None
    condition: str | None = None


class FlowLayoutIn(BaseModel):
    layout: dict


@router.get("/projects/{project_id}/flows")
def list_flows(project_id: str, db: Session = Depends(db_session)):
    return svc.list_flows(db, project_id)


@router.post("/flows", status_code=201)
def create_flow(body: FlowIn, db: Session = Depends(db_session), actor=Depends(actor)):
    f = svc.create_flow(db, **body.model_dump(), actor=actor)
    return {"id": f.id, "semantic_id": f.semantic_id, "name": f.name}


@router.post("/flow-steps", status_code=201)
def add_flow_step(body: FlowStepIn, db: Session = Depends(db_session)):
    s = svc.add_flow_step(db, **body.model_dump())
    return {"id": s.id, "semantic_id": s.semantic_id, "name": s.name, "step_type": s.step_type}


@router.post("/flow-transitions", status_code=201)
def add_flow_transition(body: FlowTransitionIn, db: Session = Depends(db_session)):
    t = svc.add_flow_transition(db, **body.model_dump())
    return {"id": t.id, "semantic_id": t.semantic_id}


@router.delete("/flow-steps/{step_id}", status_code=204)
def delete_flow_step(step_id: str, db: Session = Depends(db_session)):
    svc.delete_flow_step(db, step_id)


@router.delete("/flow-transitions/{transition_id}", status_code=204)
def delete_flow_transition(transition_id: str, db: Session = Depends(db_session)):
    svc.delete_flow_transition(db, transition_id)


@router.get("/flows/{flow_id}/layout")
def get_flow_layout(flow_id: str, db: Session = Depends(db_session)):
    f = svc.get_or_404(db, m.ProcessFlow, flow_id, "ProcessFlow")
    return f.layout or {}


@router.put("/flows/{flow_id}/layout")
def save_flow_layout(flow_id: str, body: FlowLayoutIn, db: Session = Depends(db_session)):
    svc.save_flow_layout(db, flow_id, body.layout)
    return {"ok": True}


# ---------------------------------------------------------------------------
# API design workspace
# ---------------------------------------------------------------------------


class ApiIn(BaseModel):
    project_id: str
    method: str
    path: str
    summary: str | None = None
    semantic_id: str | None = None
    description: str | None = None
    authentication: str = "NONE"


class ApiPatch(BaseModel):
    summary: str | None = None
    description: str | None = None
    authentication: str | None = None


class ApiChildIn(BaseModel):
    endpoint_id: str
    name: str
    data_type: str = "string"
    required: bool = False
    description: str | None = None
    location: str = "query"
    status_code: str = "200"
    message: str | None = None


@router.get("/projects/{project_id}/api-endpoints")
def list_api_endpoints(project_id: str, db: Session = Depends(db_session)):
    return svc.list_api_endpoints(db, project_id)


class OpenAPIImportIn(BaseModel):
    project_id: str
    document: str


@router.post("/openapi/preview")
def preview_openapi(body: OpenAPIImportIn, db: Session = Depends(db_session)):
    return svc.preview_openapi_import(db, body.project_id, body.document)


@router.post("/openapi/import")
def import_openapi(body: OpenAPIImportIn, db: Session = Depends(db_session), actor=Depends(actor)):
    return svc.import_openapi(db, body.project_id, body.document, actor=actor)


@router.get("/revisions/{revision_id}/openapi")
def export_openapi(revision_id: str, db: Session = Depends(db_session)):
    return svc.export_openapi(db, revision_id)


@router.post("/api-endpoints", status_code=201)
def create_api_endpoint(body: ApiIn, db: Session = Depends(db_session), actor=Depends(actor)):
    ep = svc.create_api_endpoint(db, **body.model_dump(), actor=actor)
    return {"id": ep.id, "semantic_id": ep.semantic_id, "method": ep.method, "path": ep.path}


@router.patch("/api-endpoints/{endpoint_id}")
def update_api_endpoint(endpoint_id: str, body: ApiPatch, db: Session = Depends(db_session)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    ep = svc.update_api_endpoint(db, endpoint_id, **changes)
    return {"id": ep.id, "semantic_id": ep.semantic_id}


@router.post("/api-parameters", status_code=201)
def add_api_parameter(body: ApiChildIn, db: Session = Depends(db_session)):
    p = svc._add_api_child(db, m.ApiParameter, endpoint_id=body.endpoint_id,
                           name=body.name, location=body.location, data_type=body.data_type,
                           required=body.required, description=body.description)
    return {"id": p.id, "name": p.name}


@router.post("/api-request-fields", status_code=201)
def add_api_request_field(body: ApiChildIn, db: Session = Depends(db_session)):
    f = svc._add_api_child(db, m.ApiRequestField, endpoint_id=body.endpoint_id,
                           name=body.name, data_type=body.data_type, required=body.required,
                           description=body.description)
    return {"id": f.id, "name": f.name}


@router.post("/api-response-fields", status_code=201)
def add_api_response_field(body: ApiChildIn, db: Session = Depends(db_session)):
    f = svc._add_api_child(db, m.ApiResponseField, endpoint_id=body.endpoint_id,
                           status_code=body.status_code, name=body.name, data_type=body.data_type,
                           description=body.description)
    return {"id": f.id, "name": f.name}


@router.post("/api-error-responses", status_code=201)
def add_api_error_response(body: ApiChildIn, db: Session = Depends(db_session)):
    e = svc._add_api_child(db, m.ApiErrorResponse, endpoint_id=body.endpoint_id,
                           status_code=body.status_code, message=body.message or body.name,
                           description=body.description)
    return {"id": e.id, "message": e.message}


@router.delete("/api-parameters/{child_id}", status_code=204)
def delete_api_parameter(child_id: str, db: Session = Depends(db_session)):
    svc._delete_api_child(db, m.ApiParameter, child_id)


@router.delete("/api-request-fields/{child_id}", status_code=204)
def delete_api_request_field(child_id: str, db: Session = Depends(db_session)):
    svc._delete_api_child(db, m.ApiRequestField, child_id)


@router.delete("/api-response-fields/{child_id}", status_code=204)
def delete_api_response_field(child_id: str, db: Session = Depends(db_session)):
    svc._delete_api_child(db, m.ApiResponseField, child_id)


@router.delete("/api-error-responses/{child_id}", status_code=204)
def delete_api_error_response(child_id: str, db: Session = Depends(db_session)):
    svc._delete_api_child(db, m.ApiErrorResponse, child_id)


# ---------------------------------------------------------------------------
# Architecture design workspace
# ---------------------------------------------------------------------------


class ArchDiagramIn(BaseModel):
    project_id: str
    name: str
    semantic_id: str
    description: str | None = None


class ArchNodeIn(BaseModel):
    diagram_id: str
    name: str
    semantic_id: str
    node_type: str = "SERVICE"
    description: str | None = None
    technology: str | None = None
    environment: str | None = None
    metadata: dict | None = None


class ArchEdgeIn(BaseModel):
    diagram_id: str
    from_node_semantic_id: str
    to_node_semantic_id: str
    label: str | None = None


class ArchLayoutIn(BaseModel):
    layout: dict


@router.get("/projects/{project_id}/architecture")
def list_architecture(project_id: str, db: Session = Depends(db_session)):
    return svc.list_architecture_diagrams(db, project_id)


@router.get("/architecture-diagrams/{diagram_id}/svg")
def architecture_diagram_svg(diagram_id: str, db: Session = Depends(db_session)):
    return Response(
        content=svc.render_architecture_diagram_svg(db, diagram_id), media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="diagram-{diagram_id}.svg"'},
    )


@router.get("/architecture-diagrams/{diagram_id}/png")
def architecture_diagram_png(diagram_id: str, db: Session = Depends(db_session)):
    return Response(
        content=svc.render_architecture_diagram_png(db, diagram_id), media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="diagram-{diagram_id}.png"'},
    )


@router.post("/architecture-diagrams", status_code=201)
def create_architecture_diagram(body: ArchDiagramIn, db: Session = Depends(db_session), actor=Depends(actor)):
    d = svc.create_architecture_diagram(db, **body.model_dump(), actor=actor)
    return {"id": d.id, "semantic_id": d.semantic_id, "name": d.name}


@router.post("/architecture-nodes", status_code=201)
def add_architecture_node(body: ArchNodeIn, db: Session = Depends(db_session)):
    n = svc.add_architecture_node(db, **body.model_dump())
    return {"id": n.id, "semantic_id": n.semantic_id, "name": n.name, "node_type": n.node_type}


@router.post("/architecture-edges", status_code=201)
def add_architecture_edge(body: ArchEdgeIn, db: Session = Depends(db_session)):
    e = svc.add_architecture_edge(db, **body.model_dump())
    return {"id": e.id, "semantic_id": e.semantic_id}


@router.delete("/architecture-nodes/{node_id}", status_code=204)
def delete_architecture_node(node_id: str, db: Session = Depends(db_session)):
    svc.delete_architecture_node(db, node_id)


@router.delete("/architecture-edges/{edge_id}", status_code=204)
def delete_architecture_edge(edge_id: str, db: Session = Depends(db_session)):
    svc.delete_architecture_edge(db, edge_id)


@router.put("/architecture-diagrams/{diagram_id}/layout")
def save_architecture_layout(diagram_id: str, body: ArchLayoutIn, db: Session = Depends(db_session)):
    svc.save_architecture_layout(db, diagram_id, body.layout)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Decision / Assumption / Clarification project memory
# ---------------------------------------------------------------------------


class DecisionIn(BaseModel):
    project_id: str
    title: str
    content: str
    decided_by: str | None = None
    related_semantic_ids: list[str] | None = None


class AssumptionIn(BaseModel):
    project_id: str
    content: str
    related_semantic_ids: list[str] | None = None


class ClarificationIn(BaseModel):
    project_id: str
    question: str
    answer: str | None = None
    related_semantic_ids: list[str] | None = None


class PromoteIn(BaseModel):
    annotation_id: str
    to_kind: str  # decision | assumption | clarification | change_request


@router.get("/projects/{project_id}/project-memory")
def list_project_memory(project_id: str, db: Session = Depends(db_session)):
    return svc.list_project_memory(db, project_id)


@router.post("/decisions", status_code=201)
def create_decision(body: DecisionIn, db: Session = Depends(db_session), actor=Depends(actor), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    d = svc.create_decision(db, **body.model_dump(), actor=actx.name, actor_id=actx.id)
    return {"id": d.id, "code": d.semantic_id, "title": d.title}


@router.post("/assumptions", status_code=201)
def create_assumption(body: AssumptionIn, db: Session = Depends(db_session), actor=Depends(actor)):
    a = svc.create_assumption(db, **body.model_dump(), actor=actor)
    return {"id": a.id, "code": a.semantic_id}


@router.post("/clarifications", status_code=201)
def create_clarification(body: ClarificationIn, db: Session = Depends(db_session), actor=Depends(actor)):
    c = svc.create_clarification(db, **body.model_dump(), actor=actor)
    return {"id": c.id, "code": c.semantic_id}


@router.post("/promote-annotation", status_code=201)
def promote_annotation(body: PromoteIn, db: Session = Depends(db_session), actor=Depends(actor)):
    return svc.promote_annotation(db, annotation_id=body.annotation_id, to_kind=body.to_kind, actor=actor)


# ---------------------------------------------------------------------------
# Reproducible export + design package
# ---------------------------------------------------------------------------


@router.get("/revisions/{revision_id}/export")
def export_revision(revision_id: str, format: str = "json", db: Session = Depends(db_session)):
    content, media_type, filename = svc.export_revision_v2(db, revision_id, format)
    return Response(
        content=content, media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/baselines/{baseline_id}/package")
def export_design_package(baseline_id: str, db: Session = Depends(db_session)):
    content = svc.export_design_package(db, baseline_id)
    return Response(
        content=content, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="baseline-{baseline_id}.zip"'},
    )


@router.get("/baselines/{baseline_id}/package-v2")
def export_design_package_v2(baseline_id: str, db: Session = Depends(db_session)):
    content = svc.export_design_package_v2(db, baseline_id)
    return Response(
        content=content, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="baseline-{baseline_id}-v2.zip"'},
    )


@router.get("/baselines/{baseline_id}/package-v4")
def export_design_package_v4(baseline_id: str, db: Session = Depends(db_session)):
    content = svc.export_design_package_v4(db, baseline_id)
    return Response(
        content=content, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="baseline-{baseline_id}-v4.zip"'},
    )


# ---------------------------------------------------------------------------
# Ecosystem event + outbox
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/ecosystem-events")
def list_ecosystem_events(project_id: str, db: Session = Depends(db_session)):
    return svc.list_ecosystem_events(db, project_id=project_id)


@router.get("/outbox")
def list_outbox(db: Session = Depends(db_session)):
    return svc.list_outbox(db)


@router.get("/outbox/{outbox_id}")
def get_outbox_event(outbox_id: str, db: Session = Depends(db_session)):
    return svc.get_outbox_event(db, outbox_id)


@router.post("/outbox/{outbox_id}/retry")
def retry_outbox_event(outbox_id: str, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    return svc.retry_outbox_event(db, outbox_id, actor_id=actx.id)


@router.get("/audit-events")
def list_audit_events(
    project_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    object_id: str | None = None,
    baseline_id: str | None = None,
    db: Session = Depends(db_session),
):
    return svc.list_audit_events(
        db, project_id=project_id, actor_id=actor_id, action=action,
        object_id=object_id, baseline_id=baseline_id,
    )


# ---------------------------------------------------------------------------
# PM / QA handoff contracts and external references
# ---------------------------------------------------------------------------


class ExecutionHandoffIn(BaseModel):
    project_id: str
    baseline_id: str | None = None
    source_revision_id: str | None = None
    change_request_id: str | None = None
    target_service: str = "pm-again"
    status: str = "DRAFT"


class QAHandoffIn(BaseModel):
    project_id: str
    baseline_id: str | None = None
    requirement_ids: list[str] | None = None
    semantic_object_ids: list[str] | None = None
    design_revision_ids: list[str] | None = None
    target_release: str | None = None
    target_service: str = "qa-again"
    status: str = "DRAFT"


class ExternalReferenceIn(BaseModel):
    project_id: str
    semantic_id: str
    service: str
    external_id: str
    relation_type: str = "TRACKED_BY"
    object_type: str | None = None
    url: str | None = None
    metadata: dict | None = None


@router.post("/handoffs/execution")
def create_execution_handoff(body: ExecutionHandoffIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.create_execution_handoff(db, **body.model_dump(), actor=actx.name, actor_id=actx.id)


@router.get("/projects/{project_id}/handoffs/execution")
def list_execution_handoffs(project_id: str, db: Session = Depends(db_session)):
    return svc.list_execution_handoffs(db, project_id=project_id)


@router.post("/handoffs/execution/{handoff_id}/deliver")
def deliver_execution_handoff(handoff_id: str, db: Session = Depends(db_session)):
    return svc.deliver_handoff_to_conductor(db, handoff_id, "execution")


@router.post("/handoffs/qa")
def create_qa_handoff(body: QAHandoffIn, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    svc.record_actor(db, actx.id, actx.name, actx.tenant_id, actx.source)
    return svc.create_qa_validation_handoff(db, **body.model_dump(), actor=actx.name, actor_id=actx.id)


@router.get("/projects/{project_id}/handoffs/qa")
def list_qa_handoffs(project_id: str, db: Session = Depends(db_session)):
    return svc.list_qa_handoffs(db, project_id=project_id)


@router.post("/handoffs/qa/{handoff_id}/deliver")
def deliver_qa_handoff(handoff_id: str, db: Session = Depends(db_session)):
    return svc.deliver_handoff_to_conductor(db, handoff_id, "qa")


@router.post("/external-references")
def create_external_reference(body: ExternalReferenceIn, db: Session = Depends(db_session)):
    return svc.create_external_reference(db, **body.model_dump())


@router.get("/projects/{project_id}/external-references")
def list_external_references(project_id: str, db: Session = Depends(db_session)):
    return svc.list_external_references(db, project_id=project_id)


@router.get("/projects/{project_id}/ecosystem-trace")
def ecosystem_trace(project_id: str, db: Session = Depends(db_session)):
    return svc.ecosystem_trace(db, project_id)


@router.get("/db-schemas/{schema_id}/data-dictionary")
def data_dictionary(schema_id: str, db: Session = Depends(db_session)):
    return svc.data_dictionary(db, schema_id)


# ---------------------------------------------------------------------------
# Document workspace (rich UR/DR content)
# ---------------------------------------------------------------------------


@router.get("/revisions/{revision_id}/document")
def get_document(revision_id: str, db: Session = Depends(db_session)):
    return svc.get_document(db, revision_id)


class DocumentIn(BaseModel):
    sections: list[dict]
    title: str | None = None


@router.put("/revisions/{revision_id}/document")
def save_document(
    revision_id: str, body: DocumentIn, db: Session = Depends(db_session),
    actor=Depends(actor),
):
    revision = svc.save_document(
        db, revision_id=revision_id, sections=body.sections, title=body.title, actor=actor
    )
    return svc.get_document(db, revision.id)


# ---------------------------------------------------------------------------
# Revision compare + semantic diff
# ---------------------------------------------------------------------------


@router.get("/revisions/{a_id}/diff/{b_id}")
def revision_diff(a_id: str, b_id: str, db: Session = Depends(db_session)):
    return svc.revision_diff(db, a_id, b_id)


class SemanticDiffIn(BaseModel):
    a: dict
    b: dict


@router.post("/diff/semantic")
def semantic_diff(body: SemanticDiffIn, db: Session = Depends(db_session)):
    return svc.semantic_diff(body.a, body.b)


class SnapshotDbIn(BaseModel):
    schema_id: str


@router.post("/revisions/{revision_id}/snapshot-database")
def snapshot_database(
    revision_id: str, body: SnapshotDbIn, db: Session = Depends(db_session),
):
    svc.snapshot_database_into_revision(db, revision_id, body.schema_id)
    return {"ok": True}
