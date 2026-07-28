import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------- Projects ----------


PROJECT_CATEGORIES = ("critical", "non_critical", "ma", "rollout")

PROJECT_CODE_RE = re.compile(r"^[A-Z]{2,4}$")


def _validate_project_code(v):
    if v is None or v == "":
        return None
    v = v.strip().upper()
    if not PROJECT_CODE_RE.match(v):
        raise ValueError("project_code must be 2-4 letters, e.g. 'CB' or 'TBOS'")
    return v


class ProjectCreate(BaseModel):
    name: str
    project_type: Optional[str] = "simple"  # simple | estimate
    project_category: Optional[str] = None  # critical | non_critical | ma | rollout
    # Running Code Generator's "PJ" prefix. Optional at creation — a project
    # can always get one later from Project Settings.
    project_code: Optional[str] = None

    @field_validator("project_type")
    @classmethod
    def validate_project_type(cls, v):
        if v not in (None, "simple", "estimate"):
            raise ValueError("project_type must be 'simple' or 'estimate'")
        return v or "simple"

    @field_validator("project_category")
    @classmethod
    def validate_project_category(cls, v):
        if v not in (None, *PROJECT_CATEGORIES):
            raise ValueError(f"project_category must be one of {PROJECT_CATEGORIES}")
        return v

    @field_validator("project_code")
    @classmethod
    def validate_project_code(cls, v):
        return _validate_project_code(v)


class ProjectUpdate(BaseModel):
    """Project Settings — currently just the running-code prefix. Kept as
    its own schema (rather than reusing ProjectCreate) so this endpoint can
    never accidentally accept a `name`/`slug` change it wasn't built for."""

    project_code: Optional[str] = None

    @field_validator("project_code")
    @classmethod
    def validate_project_code(cls, v):
        return _validate_project_code(v)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    project_type: str
    project_category: Optional[str] = None
    project_code: Optional[str] = None
    archived: bool = False
    created_at: datetime


class ProjectArchiveRequest(BaseModel):
    archived: bool
    password: str


class ProjectDeleteRequest(BaseModel):
    password: str


# ---------- Document Templates ----------


class DocumentTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_code: int
    doc_name: str
    phase_code: Optional[int] = None
    phase_name: Optional[str] = None
    doc_set_no: Optional[str] = None
    doc_set_name: Optional[str] = None
    mandatory_critical: Optional[str] = None
    mandatory_non_critical: Optional[str] = None
    mandatory_ma: Optional[str] = None
    mandatory_rollout: Optional[str] = None
    defined_by: Optional[str] = None
    documented_by: Optional[str] = None
    approved_by: Optional[str] = None


# ---------- Functions ----------


class FunctionBase(BaseModel):
    function_code: Optional[str] = None
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    phase: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = "Draft"

    # Extension fields — populated only for project_type = "estimate";
    # left None for "simple" projects.
    module: Optional[str] = None
    priority: Optional[str] = None
    scope_class: Optional[str] = None
    complexity: Optional[str] = None
    pd_ba: Optional[float] = None
    pd_ux: Optional[float] = None
    pd_fe: Optional[float] = None
    pd_be: Optional[float] = None
    pd_int_data: Optional[float] = None
    pd_qa: Optional[float] = None
    pd_devops: Optional[float] = None
    pd_total: Optional[float] = None  # server-computed; client value ignored
    performance_class: Optional[str] = None
    target_option_a: Optional[str] = None
    target_option_b: Optional[str] = None
    target_option_c: Optional[str] = None
    performance_note: Optional[str] = None
    price_thb: Optional[float] = None
    commercial_note: Optional[str] = None


class FunctionCreate(FunctionBase):
    pass


class FunctionUpdate(FunctionBase):
    name: Optional[str] = None


class FunctionOut(FunctionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# ---------- Tasks ----------


class TaskBase(BaseModel):
    task_code: Optional[str] = None
    title: str
    description: Optional[str] = None
    phase: Optional[str] = None
    owner: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = "Todo"
    priority: Optional[str] = "Med"
    is_followup: Optional[bool] = False
    linked_function_id: Optional[int] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(TaskBase):
    title: Optional[str] = None


class TaskOut(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# ---------- Gantt ----------


class GanttItemBase(BaseModel):
    name: str
    phase: Optional[str] = None
    start_date: date
    end_date: date
    progress: Optional[int] = 0
    dependencies: Optional[str] = None
    linked_task_id: Optional[int] = None
    is_milestone: Optional[bool] = False
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None


class GanttItemCreate(GanttItemBase):
    pass


class GanttItemUpdate(GanttItemBase):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class GanttItemOut(GanttItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------- Documents ----------


class DocumentBase(BaseModel):
    doc_code: Optional[str] = None
    title: str
    phase: Optional[str] = None
    doc_type: Optional[str] = None
    owner: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(DocumentBase):
    title: Optional[str] = None


class DocumentOut(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    version: int
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentSignoffCreate(BaseModel):
    signed_by: str
    signed_role: Optional[str] = None
    status: str  # Approved | Rejected
    comment: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in ("Approved", "Rejected"):
            raise ValueError("status must be 'Approved' or 'Rejected'")
        return v


class DocumentSignoffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    signed_by: str
    signed_role: Optional[str] = None
    signed_at: datetime
    status: str
    comment: Optional[str] = None


# ---------- Comments ----------


class CommentCreate(BaseModel):
    entity_type: str  # "task" | "document"
    entity_id: int
    content: str
    created_by: Optional[str] = None

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v):
        if v not in ("task", "document"):
            raise ValueError("entity_type must be 'task' or 'document'")
        return v


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    content: str
    created_by: Optional[str] = None
    created_at: datetime


# ---------- Activity Log ----------


class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: Optional[str] = None
    changed_at: datetime


# ---------- Search ----------


class SearchResult(BaseModel):
    type: str  # "function" | "task" | "document" | "note"
    id: int
    title: str
    subtitle: Optional[str] = None


# ---------- Notes ----------


class NoteCreate(BaseModel):
    content: str


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    status: str
    linked_task_id: Optional[int] = None
    linked_issue_id: Optional[int] = None
    created_at: datetime


# ---------- Effort Calculator / Change Requests ----------

WORK_TYPES = ("screen", "batch", "report")
EFFORT_ENTITY_TYPES = ("function", "task", "change_request")
IMPACT_TYPES = ("new", "modify", "delete")
CR_STATUSES = ("Draft", "UnderAnalysis", "PendingApproval", "Approved", "Rejected", "Deferred")


DELIVERY_MODES = ("human", "human_in_loop")


class EffortConfigUpdate(BaseModel):
    productivity_screen: Optional[float] = None
    productivity_batch: Optional[float] = None
    productivity_report: Optional[float] = None
    working_days_per_month: Optional[float] = None
    phase_ratio_dr: Optional[float] = None
    phase_ratio_dnpu: Optional[float] = None
    phase_ratio_iftbct: Optional[float] = None
    contracted_total_md: Optional[float] = None
    rate_thb_per_md: Optional[float] = None
    hil_leverage: Optional[dict] = None  # stored as JSON in hil_leverage_json
    hil_price_discount_percent: Optional[float] = None
    show_delivery_mode_in_client_docs: Optional[bool] = None
    hil_restricted: Optional[bool] = None


class EffortConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    productivity_screen: float
    productivity_batch: float
    productivity_report: float
    working_days_per_month: float
    phase_ratio_dr: float
    phase_ratio_dnpu: float
    phase_ratio_iftbct: float
    contracted_total_md: Optional[float] = None
    rate_thb_per_md: Optional[float] = None
    hil_leverage: Optional[dict] = None
    hil_price_discount_percent: Optional[float] = 35
    show_delivery_mode_in_client_docs: bool = False
    hil_restricted: bool = False


class EffortCalculateRequest(BaseModel):
    """Preview only — nothing is written. Drives the live preview on the form."""

    work_type: str
    driver_counts: dict = {}
    complexity: Optional[float] = None
    # Give non_similarity to set it by hand; give reusability to have it
    # derived from the 16-activity model; give neither and it defaults to 1.
    non_similarity: Optional[float] = None
    reusability: Optional[dict] = None
    priority: Optional[str] = "M"
    # Omitted entirely by anything written before Delivery Mode existed —
    # which is exactly why it defaults to "human" (multiplier 1.0).
    delivery_mode: Optional[str] = "human"

    @field_validator("work_type")
    @classmethod
    def validate_work_type(cls, v):
        if v not in WORK_TYPES:
            raise ValueError(f"work_type must be one of {WORK_TYPES}")
        return v

    @field_validator("delivery_mode")
    @classmethod
    def validate_delivery_mode(cls, v):
        if v is not None and v not in DELIVERY_MODES:
            raise ValueError(f"delivery_mode must be one of {DELIVERY_MODES}")
        return v or "human"


class EffortEstimateCreate(EffortCalculateRequest):
    linked_entity_type: str
    linked_entity_id: int

    @field_validator("linked_entity_type")
    @classmethod
    def validate_entity_type(cls, v):
        if v not in EFFORT_ENTITY_TYPES:
            raise ValueError(f"linked_entity_type must be one of {EFFORT_ENTITY_TYPES}")
        return v


class EffortEstimateUpdate(BaseModel):
    work_type: Optional[str] = None
    driver_counts: Optional[dict] = None
    complexity: Optional[float] = None
    non_similarity: Optional[float] = None
    reusability: Optional[dict] = None
    priority: Optional[str] = None
    delivery_mode: Optional[str] = None

    @field_validator("work_type")
    @classmethod
    def validate_work_type(cls, v):
        if v is not None and v not in WORK_TYPES:
            raise ValueError(f"work_type must be one of {WORK_TYPES}")
        return v

    @field_validator("delivery_mode")
    @classmethod
    def validate_delivery_mode(cls, v):
        if v is not None and v not in DELIVERY_MODES:
            raise ValueError(f"delivery_mode must be one of {DELIVERY_MODES}")
        return v


class ChangeRequestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    requested_by: Optional[str] = None
    requested_date: Optional[date] = None
    target_date: Optional[date] = None


class ChangeRequestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requested_by: Optional[str] = None
    requested_date: Optional[date] = None
    target_date: Optional[date] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in CR_STATUSES:
            raise ValueError(f"status must be one of {CR_STATUSES}")
        return v


class ChangeRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cr_code: Optional[str] = None
    title: str
    description: Optional[str] = None
    requested_by: Optional[str] = None
    requested_date: Optional[date] = None
    target_date: Optional[date] = None
    status: str
    linked_document_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ChangeRequestImpactCreate(BaseModel):
    impact_type: str
    linked_function_id: Optional[int] = None
    function_name: Optional[str] = None
    note: Optional[str] = None

    @field_validator("impact_type")
    @classmethod
    def validate_impact_type(cls, v):
        if v not in IMPACT_TYPES:
            raise ValueError(f"impact_type must be one of {IMPACT_TYPES}")
        return v


class ChangeRequestImpactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    change_request_id: int
    impact_type: str
    linked_function_id: Optional[int] = None
    function_name: Optional[str] = None
    note: Optional[str] = None


# ---------- Progress Matrix (Yotei-Jisseki) ----------

PROGRESS_ENTITY_TYPES = ("task", "function", "board_item")


class PlanDatesRequest(BaseModel):
    entity_type: str  # task | function | board_item
    entity_id: int
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v):
        if v not in PROGRESS_ENTITY_TYPES:
            raise ValueError(f"entity_type must be one of {PROGRESS_ENTITY_TYPES}")
        return v


class ActualOverrideRequest(BaseModel):
    entity_type: str  # task | function | board_item
    entity_id: int
    actual_start_override: Optional[date] = None
    actual_end_override: Optional[date] = None
    reason: Optional[str] = None
    created_by: Optional[str] = None

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v):
        if v not in PROGRESS_ENTITY_TYPES:
            raise ValueError(f"entity_type must be one of {PROGRESS_ENTITY_TYPES}")
        return v


class ActualOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    actual_start_override: Optional[date] = None
    actual_end_override: Optional[date] = None
    reason: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PlanDatesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gantt_item_id: int
    entity_type: str
    entity_id: int
    baseline_start: Optional[date] = None
    baseline_end: Optional[date] = None


# ---------- Note Pages (markdown wiki: hashtags, wiki-links, backlinks) ----------


class NotePageCreate(BaseModel):
    title: str
    content_markdown: Optional[str] = ""
    created_by: Optional[str] = None


class NotePageUpdate(BaseModel):
    title: Optional[str] = None
    content_markdown: Optional[str] = None


class NoteLinkOut(BaseModel):
    """One `[[...]]` occurrence, with where it points. `resolved=False` means
    the frontend must render it as plain text (a dead link is not an error)."""

    raw: str
    resolved: bool
    target_type: str
    target_id: Optional[int] = None
    label: str


class NotePageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content_markdown: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tags: list[str] = []
    links: list[NoteLinkOut] = []


class NotePageSummary(BaseModel):
    """List/board payload — no markdown body, so the sidebar and Tag Board
    stay light even with long notes."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tags: list[str] = []
    excerpt: Optional[str] = None


class TagCountOut(BaseModel):
    tag: str
    count: int


class LinkNoteRequest(BaseModel):
    """"Link to Note" from an entity detail page: attach an existing note by
    id, or create a new one titled `title`. Either way the backend appends
    the `[[entity_type:CODE]]` wiki-link to the note's markdown."""

    note_id: Optional[int] = None
    title: Optional[str] = None
    created_by: Optional[str] = None


class TagRenameRequest(BaseModel):
    """Tag Board drag-and-drop: move a note from one tag column to another."""

    from_tag: Optional[str] = None  # None = card dragged in from "untagged"
    to_tag: str


# ---------- Board Items (Issue / Incident / Backlog) ----------

BOARD_ITEM_TYPES = ("issue", "incident", "backlog")


class BoardItemCreate(BaseModel):
    item_type: str
    title: str
    description: Optional[str] = None
    severity: Optional[str] = None
    phase: Optional[str] = None
    owner: Optional[str] = None

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v):
        if v not in BOARD_ITEM_TYPES:
            raise ValueError(f"item_type must be one of {BOARD_ITEM_TYPES}")
        return v


class BoardItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    phase: Optional[str] = None
    owner: Optional[str] = None


class BoardItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_type: str
    item_code: Optional[str] = None
    title: str
    description: Optional[str] = None
    severity: Optional[str] = None
    status: str
    phase: Optional[str] = None
    owner: Optional[str] = None
    linked_note_id: Optional[int] = None
    linked_task_id: Optional[int] = None
    promoted_from_id: Optional[int] = None
    sla_due_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class PromoteRequest(BaseModel):
    target_type: str  # issue | incident | task

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v):
        if v not in ("issue", "incident", "task"):
            raise ValueError("target_type must be 'issue', 'incident', or 'task'")
        return v


# ---------- Gantt Annotations ----------


class GanttAnnotationCreate(BaseModel):
    gantt_date: date
    content: str
    linked_gantt_item_id: Optional[int] = None
    color: Optional[str] = "yellow"
    created_by: Optional[str] = None


class GanttAnnotationUpdate(BaseModel):
    gantt_date: Optional[date] = None
    content: Optional[str] = None
    linked_gantt_item_id: Optional[int] = None
    color: Optional[str] = None


class GanttAnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gantt_date: date
    content: str
    linked_gantt_item_id: Optional[int] = None
    color: str
    created_by: Optional[str] = None
    created_at: datetime


# ---------- Whiteboards ----------

WHITEBOARD_ENTITY_TYPES = ("project", "phase", "function", "document", "task")

BLANK_DIAGRAM_XML = (
    '<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" '
    'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="850" '
    'pageHeight="1100" math="0" shadow="0"><root><mxCell id="0" />'
    '<mxCell id="1" parent="0" /></root></mxGraphModel>'
)


class WhiteboardCreate(BaseModel):
    title: str
    xml_content: Optional[str] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[int] = None
    created_by: Optional[str] = None

    @field_validator("linked_entity_type")
    @classmethod
    def validate_linked_entity_type(cls, v):
        if v not in (None, *WHITEBOARD_ENTITY_TYPES):
            raise ValueError(f"linked_entity_type must be one of {WHITEBOARD_ENTITY_TYPES}")
        return v


class WhiteboardUpdate(BaseModel):
    title: Optional[str] = None
    xml_content: Optional[str] = None


class WhiteboardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    xml_content: Optional[str] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[int] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------- Thai Holidays ----------


class HolidayCreate(BaseModel):
    holiday_date: date
    name_th: str
    name_en: Optional[str] = None
    is_special: Optional[bool] = False


class HolidayUpdate(BaseModel):
    holiday_date: Optional[date] = None
    name_th: Optional[str] = None
    name_en: Optional[str] = None
    is_special: Optional[bool] = None


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    holiday_date: date
    name_th: str
    name_en: Optional[str] = None
    year: int
    is_special: bool


# ---------- Resources / Allocations ----------

RESOURCE_ROLES = ("SR.Arc", "DevSecOps", "SEC", "DBA", "Dev", "QA", "BA", "UX", "DevOps")


class ResourceCreate(BaseModel):
    name: str
    role: Optional[str] = None
    email: Optional[str] = None
    weekly_capacity_hours: Optional[float] = 40
    active: Optional[bool] = True

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in (None, *RESOURCE_ROLES):
            raise ValueError(f"role must be one of {RESOURCE_ROLES}")
        return v


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    weekly_capacity_hours: Optional[float] = None
    active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in (None, *RESOURCE_ROLES):
            raise ValueError(f"role must be one of {RESOURCE_ROLES}")
        return v


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: Optional[str] = None
    email: Optional[str] = None
    weekly_capacity_hours: float
    active: bool
    created_at: datetime


class ResourceAllocationCreate(BaseModel):
    resource_id: int
    linked_task_id: Optional[int] = None
    allocation_percent: int
    start_date: date
    end_date: date
    note: Optional[str] = None

    @field_validator("allocation_percent")
    @classmethod
    def validate_allocation_percent(cls, v):
        if not (0 <= v <= 100):
            raise ValueError("allocation_percent must be between 0 and 100")
        return v


class ResourceAllocationUpdate(BaseModel):
    linked_task_id: Optional[int] = None
    allocation_percent: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    note: Optional[str] = None

    @field_validator("allocation_percent")
    @classmethod
    def validate_allocation_percent(cls, v):
        if v is not None and not (0 <= v <= 100):
            raise ValueError("allocation_percent must be between 0 and 100")
        return v


class ResourceAllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    project_slug: str
    linked_task_id: Optional[int] = None
    allocation_percent: int
    start_date: date
    end_date: date
    note: Optional[str] = None
    created_at: datetime


# ---------- Auth ----------

ROLES = ("pmo_admin", "dev", "qa", "client_viewer")


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    active: bool
    must_change_password: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: str
    password: str
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("new_password must be at least 8 characters")
        return v
