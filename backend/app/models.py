"""
Conductor Again — SQLAlchemy Models
Master DB: users, refresh_tokens, project_registry
Per-project DB: project context, requirements, skills, AI resources, etc.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import MasterBase, ProjectBase


def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════
# Master DB Models
# ═══════════════════════════════════════════════════════════

class User(MasterBase):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="viewer")  # admin, conductor, approver, contributor, viewer
    active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(MasterBase):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class ProjectRegistry(MasterBase):
    __tablename__ = "project_registry"

    id = Column(String(36), primary_key=True, default=_uuid)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(String(50), default="active")  # active, archived, deleted
    # E8-C tenant isolation: owning Account Again tenant. Defaults to "local-tenant"
    # for pre-E8 projects created before tenant scoping existed (LEGACY_LOCAL_AUTH path).
    tenant_id = Column(String(100), nullable=False, default="local-tenant", index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ═══════════════════════════════════════════════════════════
# AI Resource Pool (Master DB — platform-wide)
# ═══════════════════════════════════════════════════════════

class AIProvider(MasterBase):
    """Vendor or runtime family."""
    __tablename__ = "ai_providers"

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(50), unique=True, nullable=False, index=True)  # deepseek, openai, gemini, anthropic, cloudflare, local
    name = Column(String(255), nullable=False)
    website = Column(String(500), default="")
    description = Column(Text, default="")
    logo_url = Column(String(500), default="")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    accounts = relationship("AIAccount", back_populates="provider", cascade="all, delete-orphan")


class AIAccount(MasterBase):
    """A specific account or subscription with a provider."""
    __tablename__ = "ai_accounts"

    id = Column(String(36), primary_key=True, default=_uuid)
    provider_id = Column(String(36), ForeignKey("ai_providers.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)  # e.g. "DeepSeek Company Account"
    account_type = Column(String(50), default="api")  # api, subscription, local, manual
    access_mode = Column(String(50), nullable=False, default="OFFICIAL_API")
    # OFFICIAL_API, OFFICIAL_SUBSCRIPTION_TOOL, LOCAL_MODEL, MANUAL_HANDOFF, MOCK_OR_TEST
    connector_status = Column(String(50), default="SUPPORTED")
    # SUPPORTED, PARTIALLY_SUPPORTED, MANUAL_ONLY, PLANNED, DISABLED
    api_base_url = Column(String(500), default="")
    api_key_encrypted = Column(Text, default="")  # Encrypted at rest
    api_key_last4 = Column(String(4), default="")  # Last 4 for display
    cost_center = Column(String(100), default="")
    daily_budget_usd = Column(Float, default=0.0)
    monthly_budget_usd = Column(Float, default=0.0)
    health_state = Column(String(50), default="AVAILABLE")
    # AVAILABLE, BUSY, DEGRADED, RATE_LIMITED, BUDGET_WARNING, BUDGET_EXHAUSTED,
    # OFFLINE, AUTH_EXPIRED, POLICY_BLOCKED, MANUAL_ONLY, SUSPENDED, REVOKED, UNKNOWN
    last_health_check = Column(DateTime, nullable=True)
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Float, default=0.0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    provider = relationship("AIProvider", back_populates="accounts")
    runtimes = relationship("AIExecutionRuntime", back_populates="account", cascade="all, delete-orphan")
    resources = relationship("AIResource", back_populates="account", cascade="all, delete-orphan")


class AIExecutionRuntime(MasterBase):
    """Where inference actually executes."""
    __tablename__ = "ai_execution_runtimes"

    id = Column(String(36), primary_key=True, default=_uuid)
    account_id = Column(String(36), ForeignKey("ai_accounts.id"), nullable=False, index=True)
    runtime_type = Column(String(50), default="OFFICIAL_API")
    # OFFICIAL_API, LOCAL_SERVER, DESKTOP_GPU, PRIVATE_SERVER, CLI_AGENT, MANUAL
    endpoint_url = Column(String(500), default="")
    health_state = Column(String(50), default="AVAILABLE")
    last_heartbeat = Column(DateTime, nullable=True)
    max_concurrency = Column(Integer, default=5)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    account = relationship("AIAccount", back_populates="runtimes")
    models = relationship("InstalledModel", back_populates="runtime", cascade="all, delete-orphan")


class InstalledModel(MasterBase):
    """A model available through a runtime."""
    __tablename__ = "installed_models"

    id = Column(String(36), primary_key=True, default=_uuid)
    runtime_id = Column(String(36), ForeignKey("ai_execution_runtimes.id"), nullable=False, index=True)
    model_id = Column(String(255), nullable=False)  # e.g. "deepseek-chat", "gpt-4o"
    display_name = Column(String(255), nullable=False)
    capabilities = Column(JSON, default=list)
    # TEXT_GENERATION, STRUCTURED_OUTPUT, TOOL_CALLING, VISION, DOCUMENT_UNDERSTANDING,
    # LONG_CONTEXT, CODE_REASONING, FAST_CLASSIFICATION, EMBEDDING, THAI_LANGUAGE, MULTILINGUAL
    context_limit = Column(Integer, default=8192)
    input_types = Column(JSON, default=list)    # ["text", "image", "document"]
    output_types = Column(JSON, default=list)   # ["text", "json"]
    pricing_per_1k_input = Column(Float, default=0.0)
    pricing_per_1k_output = Column(Float, default=0.0)
    latency_class = Column(String(50), default="balanced")  # fast, balanced, slow
    quality_class = Column(String(50), default="balanced")  # economical, balanced, premium
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    runtime = relationship("AIExecutionRuntime", back_populates="models")


class AIResource(MasterBase):
    """A routable combination: Account + Runtime + Model + Entitlements."""
    __tablename__ = "ai_resources"

    id = Column(String(36), primary_key=True, default=_uuid)
    account_id = Column(String(36), ForeignKey("ai_accounts.id"), nullable=False, index=True)
    runtime_id = Column(String(36), ForeignKey("ai_execution_runtimes.id"), nullable=True, index=True)
    model_id = Column(String(36), ForeignKey("installed_models.id"), nullable=True, index=True)
    display_name = Column(String(255), nullable=False)
    entitlements = Column(JSON, default=list)
    # SERVER_INFERENCE, STRUCTURED_OUTPUT, TOOL_CALLING, VISION_INPUT,
    # DOCUMENT_INPUT, CODE_AGENT, CLI_EXECUTION, LOCAL_INFERENCE, etc.
    allowed_data_classifications = Column(JSON, default=list)  # ["PUBLIC", "INTERNAL", "CONFIDENTIAL"]
    allowed_projects = Column(JSON, default=list)  # [] means all projects
    base_priority = Column(Integer, default=50)  # 0-100, higher = preferred
    max_concurrency = Column(Integer, default=3)
    current_concurrency = Column(Integer, default=0)
    health_state = Column(String(50), default="AVAILABLE")
    last_used_at = Column(DateTime, nullable=True)
    total_requests = Column(Integer, default=0)
    success_rate = Column(Float, default=1.0)
    avg_latency_ms = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    account = relationship("AIAccount", back_populates="resources")
    model = relationship("InstalledModel", foreign_keys=[model_id])
    runtime = relationship("AIExecutionRuntime", foreign_keys=[runtime_id])


# ═══════════════════════════════════════════════════════════
# Skill Registry (Master DB — platform-wide governed skills)
# ═══════════════════════════════════════════════════════════

class Skill(MasterBase):
    """A governed capability package definition."""
    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, default=_uuid)
    skill_id = Column(String(100), unique=True, nullable=False, index=True)  # e.g. "requirement-clarifier"
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    category = Column(String(100), default="")  # vision, requirement, analysis, planning, review, decision
    owner = Column(String(255), default="conductor-again")
    status = Column(String(50), default="draft")
    # draft → in_review → approved → published → deprecated → retired
    # exceptional: suspended, revoked
    execution_targets = Column(JSON, default=list)
    # CONDUCTOR_SERVER, TARGET_APP, LOCAL_AGENT, EXTERNAL_TOOL, HUMAN_ASSISTED
    capability_requirements = Column(JSON, default=dict)
    # { structuredOutput: true, toolCalling: false, minimumContextTokens: 16000, reasoningLevel: "medium" }
    model_policy = Column(JSON, default=dict)
    # { allowedProviderTypes: ["OFFICIAL_API","LOCAL_MODEL"], preferredModelClass: "balanced" }
    data_policy = Column(JSON, default=dict)
    # { maximumClassification: "INTERNAL", externalProviderAllowed: true }
    approval_policy = Column(JSON, default=dict)
    # { resultType: "AI_RECOMMENDATION", humanApprovalRequiredBefore: ["REQUIREMENT_BASELINE_CHANGE"] }
    budget_policy = Column(JSON, default=dict)
    # { maximumEstimatedCostUsd: 0.25 }
    current_version = Column(Integer, default=0)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    versions = relationship("SkillVersion", back_populates="skill", cascade="all, delete-orphan",
                            order_by="SkillVersion.version.desc()")


class SkillVersion(MasterBase):
    """Immutable published version of a Skill."""
    __tablename__ = "skill_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    skill_id = Column(String(36), ForeignKey("skills.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    checksum = Column(String(64), default="")  # SHA-256 of the package
    status = Column(String(50), default="draft")
    # draft, published, deprecated, revoked
    system_instructions = Column(Text, default="")
    prompt_template = Column(Text, default="")
    input_schema = Column(JSON, default=dict)
    output_schema = Column(JSON, default=dict)
    tool_permissions = Column(JSON, default=list)
    examples = Column(JSON, default=list)
    evaluation_suite_ref = Column(String(500), default="")
    dependencies = Column(JSON, default=list)
    release_notes = Column(Text, default="")
    published_by = Column(String(255), default="")
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    skill = relationship("Skill", back_populates="versions")
    executions = relationship("SkillExecution", back_populates="skill_version", cascade="all, delete-orphan")


class SkillAssignment(MasterBase):
    """Assigns a Skill version to a project, role, or workflow."""
    __tablename__ = "skill_assignments"

    id = Column(String(36), primary_key=True, default=_uuid)
    skill_version_id = Column(String(36), ForeignKey("skill_versions.id"), nullable=False, index=True)
    scope_type = Column(String(50), nullable=False)  # platform, application, project, role, workflow
    scope_value = Column(String(255), default="")  # project slug, role name, workflow type
    assigned_by = Column(String(255), default="")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    revoked_at = Column(DateTime, nullable=True)


class SkillExecution(MasterBase):
    """Record of a Skill being executed through an AI resource."""
    __tablename__ = "skill_executions"

    id = Column(String(36), primary_key=True, default=_uuid)
    skill_version_id = Column(String(36), ForeignKey("skill_versions.id"), nullable=False, index=True)
    resource_id = Column(String(36), ForeignKey("ai_resources.id"), nullable=True)
    project_slug = Column(String(100), default="")
    request_id = Column(String(100), default="")
    selection_mode = Column(String(50), default="AUTO")  # AUTO, PIN_RESOURCE, MANUAL_HANDOFF
    status = Column(String(50), default="queued")
    # queued, running, succeeded, failed_retryable, failed_final, rejected_by_policy, cancelled
    input_summary = Column(Text, default="")
    output_summary = Column(Text, default="")
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    confidence = Column(Float, nullable=True)
    result_type = Column(String(50), default="AI_RECOMMENDATION")
    # AI_RECOMMENDATION, RULE_RESULT, HUMAN_DECISION, MACHINE_ASSERTION
    warnings = Column(JSON, default=list)
    error_message = Column(Text, default="")
    executed_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    skill_version = relationship("SkillVersion", back_populates="executions")


# ═══════════════════════════════════════════════════════════
# Multi-Agent Deliberation & Anti-Convergence (Master DB)
# ═══════════════════════════════════════════════════════════

class DeliberationCase(MasterBase):
    """A governed multi-agent deliberation session."""
    __tablename__ = "deliberation_cases"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_slug = Column(String(100), default="", index=True)
    title = Column(String(500), nullable=False)
    trigger = Column(String(100), default="")  # HIGH_IMPACT, LOW_CONFIDENCE, CONFLICTING_REQUIREMENTS, etc.
    skill_id = Column(String(36), ForeignKey("skills.id"), nullable=True)
    status = Column(String(50), default="draft")
    # draft → source_packet_frozen → panel_selected → independent_round → independent_complete
    # → blind_review → private_revision → diversity_check → judging → waiting_for_human → decided
    # alternative: insufficient_diversity, conformity_alert, evidence_required, fresh_panel_required, cancelled
    source_packet_json = Column(JSON, default=dict)  # Frozen input for all panel members
    decision_criteria = Column(Text, default="")
    outcome = Column(String(50), nullable=True)
    # SUPPORTED_AGREEMENT, SUPPORTED_MAJORITY_WITH_DISSENT, UNRESOLVED_DISAGREEMENT,
    # INSUFFICIENT_EVIDENCE, HUMAN_DECISION_REQUIRED, ADDITIONAL_EXPERIMENT_REQUIRED
    final_decision = Column(Text, default="")
    decided_by = Column(String(255), default="")
    decided_at = Column(DateTime, nullable=True)
    human_approved = Column(Boolean, default=False)
    human_approved_by = Column(String(255), default="")
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    members = relationship("PanelMember", back_populates="case", cascade="all, delete-orphan")
    submissions = relationship("IndependentSubmission", back_populates="case", cascade="all, delete-orphan")
    critiques = relationship("PeerCritique", back_populates="case", cascade="all, delete-orphan")
    dissents = relationship("DissentRecord", back_populates="case", cascade="all, delete-orphan")
    snapshots = relationship("DiversitySnapshot", back_populates="case", cascade="all, delete-orphan")


class PanelMember(MasterBase):
    """A panel member with assigned role and resource."""
    __tablename__ = "panel_members"

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("deliberation_cases.id"), nullable=False, index=True)
    resource_id = Column(String(36), ForeignKey("ai_resources.id"), nullable=True)
    assigned_role = Column(String(50), nullable=False)
    # PROPOSER, ALTERNATIVE_PROPOSER, DOMAIN_ANALYST, ASSUMPTION_CHALLENGER,
    # EVIDENCE_CHECKER, RISK_ANALYST, RED_TEAM, INDEPENDENT_JUDGE, JURY_MEMBER
    provider_code = Column(String(50), default="")  # For diversity tracking
    model_id = Column(String(255), default="")
    display_label = Column(String(50), default="")  # Candidate A, B, C...
    has_submitted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

    case = relationship("DeliberationCase", back_populates="members")


class IndependentSubmission(MasterBase):
    """Immutable first-pass submission — member sees NO peer answers."""
    __tablename__ = "independent_submissions"

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("deliberation_cases.id"), nullable=False, index=True)
    member_id = Column(String(36), ForeignKey("panel_members.id"), nullable=False)
    conclusion = Column(Text, default="")
    recommended_action = Column(Text, default="")
    key_claims = Column(JSON, default=list)
    evidence_references = Column(JSON, default=list)
    assumptions = Column(JSON, default=list)
    uncertainties = Column(JSON, default=list)
    limitations = Column(JSON, default=list)
    counterarguments = Column(JSON, default=list)
    failure_conditions = Column(JSON, default=list)
    confidence = Column(Float, nullable=True)  # 0.0 - 1.0
    evidence_quality = Column(Float, nullable=True)  # 0.0 - 1.0
    what_would_change_conclusion = Column(Text, default="")
    raw_response = Column(Text, default="")
    is_immutable = Column(Boolean, default=True)  # Original always preserved
    submitted_at = Column(DateTime, default=_utcnow)

    case = relationship("DeliberationCase", back_populates="submissions")


class PeerCritique(MasterBase):
    """Blind peer review: anonymized, order-randomized."""
    __tablename__ = "peer_critiques"

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("deliberation_cases.id"), nullable=False, index=True)
    reviewer_member_id = Column(String(36), ForeignKey("panel_members.id"), nullable=False)
    target_submission_id = Column(String(36), ForeignKey("independent_submissions.id"), nullable=False)
    target_label = Column(String(50), default="")  # Blind label (Candidate A)
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    evidence_gaps = Column(JSON, default=list)
    logical_issues = Column(JSON, default=list)
    overall_assessment = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    case = relationship("DeliberationCase", back_populates="critiques")


class OpinionRevision(MasterBase):
    """Tracked opinion change after critique — must cite evidence."""
    __tablename__ = "opinion_revisions"

    id = Column(String(36), primary_key=True, default=_uuid)
    original_submission_id = Column(String(36), ForeignKey("independent_submissions.id"), nullable=False)
    member_id = Column(String(36), ForeignKey("panel_members.id"), nullable=False)
    previous_conclusion = Column(Text, default="")
    new_conclusion = Column(Text, default="")
    changed = Column(Boolean, default=False)
    new_evidence_received = Column(JSON, default=list)
    critique_accepted = Column(JSON, default=list)
    critique_rejected = Column(JSON, default=list)
    assumption_changed = Column(Text, default="")
    confidence_before = Column(Float, nullable=True)
    confidence_after = Column(Float, nullable=True)
    reason_for_change = Column(Text, default="")
    potential_conformity_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)


class DissentRecord(MasterBase):
    """Preserved minority position — never deleted on majority decision."""
    __tablename__ = "dissent_records"

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("deliberation_cases.id"), nullable=False, index=True)
    member_id = Column(String(36), ForeignKey("panel_members.id"), nullable=False)
    position = Column(Text, default="")
    supporting_evidence = Column(JSON, default=list)
    rejected_majority_assumptions = Column(JSON, default=list)
    risk_if_minority_correct = Column(Text, default="")
    suggested_verification = Column(Text, default="")
    status = Column(String(50), default="open")  # open, acknowledged, accepted, resolved
    resolution_note = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    case = relationship("DeliberationCase", back_populates="dissents")


class DiversitySnapshot(MasterBase):
    """Anti-convergence metric snapshot taken at each deliberation stage."""
    __tablename__ = "diversity_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("deliberation_cases.id"), nullable=False, index=True)
    stage = Column(String(50), default="")  # initial, after_critique, after_revision, final
    initial_conclusion_diversity = Column(Float, default=0.0)
    provider_concentration = Column(Float, default=0.0)  # 0 = diverse, 1 = all same
    model_family_concentration = Column(Float, default=0.0)
    disagreement_rate = Column(Float, default=0.0)
    opinion_change_rate = Column(Float, default=0.0)
    majority_attraction_rate = Column(Float, default=0.0)  # % who moved toward majority
    unsupported_agreement_rate = Column(Float, default=0.0)
    minority_survival_rate = Column(Float, default=0.0)
    confidence_synchronization = Column(Float, default=0.0)
    conformity_alerts = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utcnow)

    case = relationship("DeliberationCase", back_populates="snapshots")


# ═══════════════════════════════════════════════════════════
# AI Governance — Execution Leases, Routing Decisions, Snapshots
# ═══════════════════════════════════════════════════════════

class ExecutionLease(MasterBase):
    """Prevents duplicate execution, concurrency overcommit, fallback storms."""
    __tablename__ = "execution_leases"

    id = Column(String(36), primary_key=True, default=_uuid)
    resource_id = Column(String(36), ForeignKey("ai_resources.id"), nullable=False, index=True)
    request_id = Column(String(100), default="")
    workflow_id = Column(String(100), default="")
    project_slug = Column(String(100), default="")
    concurrency_slot = Column(Integer, default=0)
    status = Column(String(50), default="active")  # active, released, expired
    acquired_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)
    release_reason = Column(String(100), default="")  # completed, failed, timeout, cancelled


class RoutingDecision(MasterBase):
    """Explainable routing decision: Primary, Fallbacks, Escalation."""
    __tablename__ = "routing_decisions"

    id = Column(String(36), primary_key=True, default=_uuid)
    request_id = Column(String(100), default="", index=True)
    project_slug = Column(String(100), default="")
    selection_mode = Column(String(50), default="AUTO")
    # AUTO, AUTO_PREFER_LOCAL, AUTO_PRIVATE_ONLY, AUTO_LOWEST_COST,
    # AUTO_HIGHEST_QUALITY, AUTO_FASTEST, PIN_RESOURCE, MANUAL_HANDOFF_ONLY
    selected_primary_resource_id = Column(String(36), ForeignKey("ai_resources.id"), nullable=True)
    fallback_resource_ids = Column(JSON, default=list)
    escalation_resource_id = Column(String(36), ForeignKey("ai_resources.id"), nullable=True)
    candidate_count = Column(Integer, default=0)
    eligible_count = Column(Integer, default=0)
    decision_policy_version = Column(String(50), default="")
    reason = Column(JSON, default=list)
    # List of human-readable reasons
    candidate_details = Column(JSON, default=list)
    # Per-candidate: { resourceId, eligible, totalScore, components, warnings, rejectionReason }
    created_at = Column(DateTime, default=_utcnow)


class HealthSnapshot(MasterBase):
    """Time-stamped health observation for an AI resource."""
    __tablename__ = "health_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    resource_id = Column(String(36), ForeignKey("ai_resources.id"), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("ai_accounts.id"), nullable=True, index=True)
    state = Column(String(50), default="AVAILABLE")
    message = Column(Text, default="")
    latency_ms = Column(Integer, default=0)
    observed_at = Column(DateTime, default=_utcnow)


class QuotaSnapshot(MasterBase):
    """Quota/reset observation for an account."""
    __tablename__ = "quota_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    account_id = Column(String(36), ForeignKey("ai_accounts.id"), nullable=False, index=True)
    requests_used = Column(Integer, default=0)
    requests_limit = Column(Integer, nullable=True)
    tokens_used = Column(Integer, default=0)
    tokens_limit = Column(Integer, nullable=True)
    reset_at = Column(DateTime, nullable=True)
    source = Column(String(50), default="OBSERVED")  # OBSERVED, PROVIDER_API, MANUAL, UNAVAILABLE
    confidence = Column(String(50), default="MEDIUM")  # HIGH, MEDIUM, LOW, UNKNOWN
    observed_at = Column(DateTime, default=_utcnow)


class BudgetSnapshot(MasterBase):
    """Budget consumption observation."""
    __tablename__ = "budget_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    account_id = Column(String(36), ForeignKey("ai_accounts.id"), nullable=False, index=True)
    daily_spent_usd = Column(Float, default=0.0)
    monthly_spent_usd = Column(Float, default=0.0)
    total_spent_usd = Column(Float, default=0.0)
    observed_at = Column(DateTime, default=_utcnow)


# ═══════════════════════════════════════════════════════════
# Anti-Convergence — Conformity Alerts, Decision Rubric, Recovery
# ═══════════════════════════════════════════════════════════

class ConformityAlert(MasterBase):
    """Raised when anti-convergence metrics trigger a policy threshold."""
    __tablename__ = "conformity_alerts"

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("deliberation_cases.id"), nullable=False, index=True)
    alert_type = Column(String(100), default="")
    # MAJORITY_FOLLOWING, DIVERSITY_COLLAPSE, UNSUPPORTED_AGREEMENT,
    # CONFIDENCE_SYNCHRONIZATION, MINORITY_SUPPRESSION, AUTHORITY_BIAS,
    # PROVIDER_CONCENTRATION, SEMANTIC_COLLAPSE
    severity = Column(String(50), default="warning")  # info, warning, critical
    description = Column(Text, default="")
    metrics_snapshot = Column(JSON, default=dict)
    recommended_action = Column(String(100), default="")
    # FREEZE_CURRENT_DECISION, REQUEST_HUMAN_REVIEW, SPAWN_FRESH_PANEL,
    # ADD_DIFFERENT_PROVIDER, RESET_CONTEXT, RUN_DETERMINISTIC_CHECK
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(255), default="")
    created_at = Column(DateTime, default=_utcnow)


class DecisionRubric(MasterBase):
    """Explicit scoring rubric used by a judge for a deliberation."""
    __tablename__ = "decision_rubrics"

    id = Column(String(36), primary_key=True, default=_uuid)
    case_id = Column(String(36), ForeignKey("deliberation_cases.id"), nullable=False, index=True)
    criteria = Column(JSON, default=list)
    # [{ name, weight, description, maxScore }]
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=_utcnow)


class JudgeScore(MasterBase):
    """A judge's scored evaluation of one candidate against the rubric."""
    __tablename__ = "judge_scores"

    id = Column(String(36), primary_key=True, default=_uuid)
    rubric_id = Column(String(36), ForeignKey("decision_rubrics.id"), nullable=False, index=True)
    case_id = Column(String(36), ForeignKey("deliberation_cases.id"), nullable=False, index=True)
    judge_member_id = Column(String(36), ForeignKey("panel_members.id"), nullable=False)
    candidate_label = Column(String(50), default="")  # Blind label
    submission_id = Column(String(36), ForeignKey("independent_submissions.id"), nullable=False)
    scores = Column(JSON, default=dict)  # { criterionName: score }
    total_score = Column(Float, default=0.0)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)


class RecoveryAction(MasterBase):
    """Action taken in response to a ConformityAlert or policy trigger."""
    __tablename__ = "recovery_actions"

    id = Column(String(36), primary_key=True, default=_uuid)
    alert_id = Column(String(36), ForeignKey("conformity_alerts.id"), nullable=True, index=True)
    case_id = Column(String(36), ForeignKey("deliberation_cases.id"), nullable=True, index=True)
    action_type = Column(String(100), nullable=False)
    # FREEZE_CURRENT_DECISION, REQUEST_HUMAN_REVIEW, SPAWN_FRESH_PANEL,
    # ADD_DIFFERENT_PROVIDER, ADD_LOCAL_MODEL, ADD_RED_TEAM,
    # RESET_CONTEXT_FROM_SOURCE_ARTIFACTS, REQUEST_NEW_EVIDENCE,
    # RUN_DETERMINISTIC_CHECK, USE_CONSENSUS_FREE_SCORING,
    # PRESERVE_MINORITY_AS_BLOCKING_RISK
    trigger_reason = Column(Text, default="")
    status = Column(String(50), default="pending")  # pending, executed, failed, cancelled
    result = Column(Text, default="")
    executed_by = Column(String(255), default="")
    created_at = Column(DateTime, default=_utcnow)
    executed_at = Column(DateTime, nullable=True)


# ═══════════════════════════════════════════════════════════
# Integration Outbox (Master DB)
# ═══════════════════════════════════════════════════════════

class OutboxMessage(MasterBase):
    """Transactional outbox for reliable integration event publication."""
    __tablename__ = "outbox"

    id = Column(String(36), primary_key=True, default=_uuid)
    message_type = Column(String(100), nullable=False)  # Command or Event
    aggregate_type = Column(String(100), default="")
    aggregate_id = Column(String(36), default="")
    event_type = Column(String(255), nullable=False)
    payload_json = Column(Text, default="{}")
    correlation_id = Column(String(100), default="")
    causation_id = Column(String(100), default="")
    idempotency_key = Column(String(255), default="", index=True)
    status = Column(String(50), default="pending")  # pending, published, failed, dead_letter
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=5)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)
    published_at = Column(DateTime, nullable=True)


# ═══════════════════════════════════════════════════════════
# Integration Registry (Master DB)
# ═══════════════════════════════════════════════════════════

class IntegrationService(MasterBase):
    """Registered sibling Again Platform service."""
    __tablename__ = "integration_services"

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(50), unique=True, nullable=False, index=True)  # pm-again, qa-again, dev-again
    name = Column(String(255), nullable=False)
    base_url = Column(String(500), default="")
    service_token_encrypted = Column(Text, default="")
    status = Column(String(50), default="CONNECTED")
    # CONNECTED, PENDING_DEPLOYMENT, PLANNED, DEGRADED, DISABLED
    last_health_check = Column(DateTime, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


# ═══════════════════════════════════════════════════════════
# Per-Project DB Models
# ═══════════════════════════════════════════════════════════

class ArtifactReference(ProjectBase):
    """A reference to an artifact owned by another Again Platform app."""
    __tablename__ = "artifact_references"

    id = Column(String(36), primary_key=True, default=_uuid)
    owner_system = Column(String(50), nullable=False)  # PM_AGAIN, QA_AGAIN, DEV
    artifact_type = Column(String(50), nullable=False)  # EPIC, FEATURE, TASK, TEST_CASE, DEFECT
    external_id = Column(String(255), nullable=False)   # ID in the owning system
    external_url = Column(String(1000), default="")
    display_key = Column(String(255), default="")
    status = Column(String(50), default="")             # latest observed status
    metadata_json = Column(JSON, default=dict)
    last_observed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)


class TraceLink(ProjectBase):
    """A traceability link between two artifacts (could be cross-system)."""
    __tablename__ = "trace_links"

    id = Column(String(36), primary_key=True, default=_uuid)
    source_type = Column(String(50), nullable=False)   # VISION, REQUIREMENT, FUNCTION
    source_id = Column(String(36), nullable=False)     # Local artifact ID
    target_type = Column(String(50), nullable=False)   # EPIC, FEATURE, TASK, TEST_CASE, DEFECT
    target_ref_id = Column(String(36), ForeignKey("artifact_references.id"), nullable=False)
    link_type = Column(String(50), default="traces_to")  # traces_to, derived_from, verified_by
    created_at = Column(DateTime, default=_utcnow)


class Vision(ProjectBase):
    __tablename__ = "visions"

    id = Column(String(36), primary_key=True, default=_uuid)
    revision = Column(Integer, nullable=False, default=1)
    content = Column(Text, nullable=False)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class Objective(ProjectBase):
    __tablename__ = "objectives"

    id = Column(String(36), primary_key=True, default=_uuid)
    vision_id = Column(String(36), ForeignKey("visions.id"), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)


class Requirement(ProjectBase):
    __tablename__ = "requirements"

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    status = Column(String(50), default="draft")  # draft, clarifying, approved, change_proposed, superseded
    revision = Column(Integer, default=1)
    baseline_approved = Column(Boolean, default=False)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class ActivityLog(ProjectBase):
    __tablename__ = "activity_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    actor = Column(String(255), nullable=False)
    actor_type = Column(String(50), nullable=False, default="human")  # human, ai, rule, system
    action = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(36), nullable=False)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)


# ═══════════════════════════════════════════════════════════
# Intake & Decomposition (Per-Project DB)
# ═══════════════════════════════════════════════════════════

class IntakeSession(ProjectBase):
    """A user intake session: upload text → decompose → analyze."""
    __tablename__ = "intake_sessions"

    id = Column(String(36), primary_key=True, default=_uuid)
    source_type = Column(String(50), default="text")  # text, excel, markdown, image, ppt
    source_name = Column(String(500), default="")
    raw_content = Column(Text, default="")
    status = Column(String(50), default="draft")  # draft, decomposed, analyzed, distributed
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=_utcnow)


class FunctionItem(ProjectBase):
    """A decomposed function/feature from intake analysis."""
    __tablename__ = "function_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("intake_sessions.id"), nullable=False, index=True)
    code = Column(String(50), default="")            # F-001, F-002...
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    category = Column(String(100), default="")       # ui, backend, integration, data, security, reporting
    complexity_score = Column(Float, default=0.0)
    complexity_level = Column(String(50), default="")
    complexity_breakdown = Column(JSON, default=dict)
    effort_fp = Column(Float, default=0.0)          # Function points
    effort_person_days = Column(Float, default=0.0)
    effort_level = Column(String(50), default="")
    effort_breakdown = Column(JSON, default=dict)
    priority = Column(Integer, default=0)            # 0=auto, 1-5 manual
    dependencies = Column(JSON, default=list)        # Other function codes this depends on
    target_module = Column(String(100), default="")  # PM_AGAIN, QA_AGAIN, DEV, CONDUCTOR
    assigned_to = Column(String(255), default="")
    status = Column(String(50), default="identified")
    # identified, estimated, assigned, in_progress, completed
    created_at = Column(DateTime, default=_utcnow)


class SimilarityPair(ProjectBase):
    """Detected similarity between two functions."""
    __tablename__ = "similarity_pairs"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("intake_sessions.id"), nullable=False, index=True)
    function_a_id = Column(String(36), ForeignKey("function_items.id"), nullable=False)
    function_b_id = Column(String(36), ForeignKey("function_items.id"), nullable=False)
    score = Column(Float, default=0.0)
    level = Column(String(50), default="none")  # none, low, medium, high, duplicate
    shared_keywords = Column(JSON, default=list)
    recommendation = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)


class RiskAssessment(ProjectBase):
    """Risk forecast for a decomposed function set."""
    __tablename__ = "risk_assessments"

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("intake_sessions.id"), nullable=False, index=True)
    overall_risk_score = Column(Float, default=0.0)
    level = Column(String(50), default="low")
    schedule_buffer_days = Column(Integer, default=0)
    summary = Column(Text, default="")
    risk_items = Column(JSON, default=list)  # Serialized RiskItem list
    created_at = Column(DateTime, default=_utcnow)
