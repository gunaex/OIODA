"""
Conductor Again — Pydantic Schemas
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Auth ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    active: bool
    must_change_password: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── Projects ──────────────────────────────────────────────

class ProjectCreate(BaseModel):
    slug: str
    name: str
    description: str = ""


class ProjectOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


# ── Vision ────────────────────────────────────────────────

class VisionCreate(BaseModel):
    content: str


class VisionOut(BaseModel):
    id: str
    revision: int
    content: str
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Requirements ──────────────────────────────────────────

class RequirementCreate(BaseModel):
    code: str
    title: str
    description: str = ""


class RequirementOut(BaseModel):
    id: str
    code: str
    title: str
    description: str
    status: str
    revision: int
    baseline_approved: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Activity ──────────────────────────────────────────────

class ActivityOut(BaseModel):
    id: str
    actor: str
    actor_type: str
    action: str
    entity_type: str
    entity_id: str
    details: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── AI Providers ──────────────────────────────────────────

class AIProviderCreate(BaseModel):
    code: str
    name: str
    website: str = ""
    description: str = ""
    logo_url: str = ""


class AIProviderOut(BaseModel):
    id: str
    code: str
    name: str
    website: str
    description: str
    logo_url: str
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── AI Accounts ───────────────────────────────────────────

class AIAccountCreate(BaseModel):
    provider_id: str
    name: str
    account_type: str = "api"
    access_mode: str = "OFFICIAL_API"
    connector_status: str = "SUPPORTED"
    api_base_url: str = ""
    api_key: str = ""  # Only on create — never returned
    cost_center: str = ""
    daily_budget_usd: float = 0.0
    monthly_budget_usd: float = 0.0


class AIAccountUpdate(BaseModel):
    name: str | None = None
    account_type: str | None = None
    access_mode: str | None = None
    connector_status: str | None = None
    api_base_url: str | None = None
    api_key: str | None = None
    cost_center: str | None = None
    daily_budget_usd: float | None = None
    monthly_budget_usd: float | None = None
    health_state: str | None = None
    enabled: bool | None = None


class AIAccountOut(BaseModel):
    id: str
    provider_id: str
    name: str
    account_type: str
    access_mode: str
    connector_status: str
    api_base_url: str
    api_key_last4: str
    cost_center: str
    daily_budget_usd: float
    monthly_budget_usd: float
    health_state: str
    last_health_check: datetime | None
    total_requests: int
    total_tokens: int
    total_cost_usd: float
    enabled: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


# ── AI Execution Runtimes ─────────────────────────────────

class AIRuntimeCreate(BaseModel):
    account_id: str
    runtime_type: str = "OFFICIAL_API"
    endpoint_url: str = ""
    max_concurrency: int = 5


class AIRuntimeOut(BaseModel):
    id: str
    account_id: str
    runtime_type: str
    endpoint_url: str
    health_state: str
    last_heartbeat: datetime | None
    max_concurrency: int
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Installed Models ──────────────────────────────────────

class InstalledModelCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    runtime_id: str
    model_id: str
    display_name: str
    capabilities: list[str] = []
    context_limit: int = 8192
    input_types: list[str] = ["text"]
    output_types: list[str] = ["text"]
    pricing_per_1k_input: float = 0.0
    pricing_per_1k_output: float = 0.0
    latency_class: str = "balanced"
    quality_class: str = "balanced"


class InstalledModelOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)
    id: str
    runtime_id: str
    model_id: str
    display_name: str
    capabilities: list[str]
    context_limit: int
    input_types: list[str]
    output_types: list[str]
    pricing_per_1k_input: float
    pricing_per_1k_output: float
    latency_class: str
    quality_class: str
    enabled: bool
    created_at: datetime


# ── AI Resources (routable combinations) ──────────────────

class AIResourceCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    account_id: str
    runtime_id: str | None = None
    model_id: str | None = None
    display_name: str
    entitlements: list[str] = []
    allowed_data_classifications: list[str] = ["PUBLIC", "INTERNAL"]
    allowed_projects: list[str] = []
    base_priority: int = 50
    max_concurrency: int = 3


class AIResourceOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)
    id: str
    account_id: str
    runtime_id: str | None
    model_id: str | None
    display_name: str
    entitlements: list[str]
    allowed_data_classifications: list[str]
    allowed_projects: list[str]
    base_priority: int
    max_concurrency: int
    current_concurrency: int
    health_state: str
    last_used_at: datetime | None
    total_requests: int
    success_rate: float
    avg_latency_ms: int
    enabled: bool
    created_at: datetime


# ── AI Resource Pool Summary ──────────────────────────────

class AIResourcePoolSummary(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    total_resources: int
    available: int
    busy: int
    degraded: int
    offline: int
    rate_limited: int
    provider_count: int
    account_count: int
    model_count: int


# ── Skills ────────────────────────────────────────────────

class SkillCreate(BaseModel):
    model_config = {"protected_namespaces": ()}
    skill_id: str
    name: str
    description: str = ""
    category: str = ""
    execution_targets: list[str] = []
    capability_requirements: dict = {}
    model_policy: dict = {}
    data_policy: dict = {}
    approval_policy: dict = {}
    budget_policy: dict = {}


class SkillOut(BaseModel):
    model_config = {"protected_namespaces": (), "from_attributes": True}
    id: str
    skill_id: str
    name: str
    description: str
    category: str
    owner: str
    status: str
    execution_targets: list[str]
    capability_requirements: dict
    model_policy: dict
    data_policy: dict
    approval_policy: dict
    budget_policy: dict
    current_version: int
    created_by: str
    created_at: datetime
    updated_at: datetime | None


class SkillVersionCreate(BaseModel):
    skill_db_id: str  # FK to skills.id
    system_instructions: str = ""
    prompt_template: str = ""
    input_schema: dict = {}
    output_schema: dict = {}
    tool_permissions: list[str] = []
    examples: list[dict] = []
    dependencies: list[str] = []
    release_notes: str = ""


class SkillVersionOut(BaseModel):
    id: str
    skill_id: str
    version: int
    checksum: str
    status: str
    system_instructions: str
    prompt_template: str
    input_schema: dict
    output_schema: dict
    tool_permissions: list[str]
    examples: list[dict]
    dependencies: list[str]
    release_notes: str
    published_by: str
    published_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class SkillAssignmentCreate(BaseModel):
    skill_version_id: str
    scope_type: str  # platform, application, project, role, workflow
    scope_value: str = ""


class SkillAssignmentOut(BaseModel):
    id: str
    skill_version_id: str
    scope_type: str
    scope_value: str
    assigned_by: str
    active: bool
    created_at: datetime
    revoked_at: datetime | None

    class Config:
        from_attributes = True


# ── Skill Execution ───────────────────────────────────────

class SkillExecuteRequest(BaseModel):
    skill_id: str  # e.g. "requirement-clarifier"
    project_slug: str = ""
    input_data: dict = {}
    selection_mode: str = "AUTO"  # AUTO, PIN_RESOURCE
    pin_resource_id: str | None = None


class SkillExecutionOut(BaseModel):
    id: str
    skill_version_id: str
    resource_id: str | None
    project_slug: str
    request_id: str
    selection_mode: str
    status: str
    input_summary: str
    output_summary: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: int
    confidence: float | None
    result_type: str
    warnings: list[str]
    error_message: str
    executed_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


# ── Auto Router Decision ──────────────────────────────────

class RouterCandidateOut(BaseModel):
    resource_id: str
    display_name: str
    eligible: bool
    total_score: float
    rejection_reason: str = ""
    components: dict = {}


class RouterDecisionOut(BaseModel):
    request_id: str
    skill_id: str
    selection_mode: str
    primary_resource_id: str | None
    primary_display_name: str = ""
    fallback_ids: list[str] = []
    escalation_id: str | None = None
    candidates_considered: int
    candidates_eligible: int
    reason: list[str] = []
    # E8.1-E: AUTO-router chooses the candidate; execution itself always routes through
    # the AIExecutionGateway (LocalAIControlCenterClient), never a direct provider call.
    # None when no eligible candidate existed to execute.
    execution: dict | None = None
