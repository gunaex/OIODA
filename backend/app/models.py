from datetime import datetime, date

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Float,
    UniqueConstraint,
)

from .database import MasterBase, ProjectBase

# Canonical phase sequence (matches document_templates.phase_code 10..90) —
# used to sort phase-keyed results in business order rather than
# alphabetically (alphabetical would put DN before DR before... UR last).
PHASE_ORDER = ["UR", "DR", "DN", "PU", "ST", "UT", "TR", "IP", "MA"]


def phase_sort_key(phase: str | None) -> int:
    if phase in PHASE_ORDER:
        return PHASE_ORDER.index(phase)
    return len(PHASE_ORDER)  # unrecognized/"Unspecified" phases sort last


class Project(MasterBase):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    project_type = Column(String, default="simple")  # simple | estimate
    project_category = Column(String, nullable=True)  # critical | non_critical | ma | rollout
    notification_email = Column(String, nullable=True)  # reserved for future email alerts
    archived = Column(Boolean, default=False)  # hidden from the default project list, not deleted
    # Running Code Generator's "PJ" prefix (e.g. "CB", "TB") — 2-4 uppercase
    # letters. Nullable: a project created before this feature, or one that
    # never sets it, just keeps typing task/function codes by hand.
    project_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


ROLES = ("pmo_admin", "dev", "qa", "client_viewer")


class User(MasterBase):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # pmo_admin | dev | qa | client_viewer
    active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RefreshToken(MasterBase):
    """Opaque refresh tokens, stored hashed (never the raw token) so a DB
    leak alone doesn't hand out working credentials. Revocable on logout."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ThaiHoliday(MasterBase):
    """Global reference table (master.db) — company-wide, not per-project,
    same reasoning as Resource. Feeds business_day.py's is_business_day."""

    __tablename__ = "thai_holidays"

    id = Column(Integer, primary_key=True, index=True)
    holiday_date = Column(Date, nullable=False, unique=True, index=True)
    name_th = Column(String, nullable=False)
    name_en = Column(String, nullable=True)
    year = Column(Integer, nullable=False, index=True)
    is_special = Column(Boolean, default=False)  # ad-hoc cabinet-announced bridge day, not a fixed annual occasion


RESOURCE_ROLES =("SR.Arc", "DevSecOps", "SEC", "DBA", "Dev", "QA", "BA", "UX", "DevOps")


class Resource(MasterBase):
    """A person, company-wide — lives in master.db (not per-project) since
    the same person can be allocated across multiple projects at once."""

    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=True)
    email = Column(String, nullable=True)
    weekly_capacity_hours = Column(Float, default=40)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ResourceAllocation(MasterBase):
    """project_slug is a plain string reference, not a cross-DB FK — the
    project's own data lives in a separate SQLite file per the existing
    architecture, so referential integrity here is enforced in application
    code (checking the project exists) rather than at the DB level."""

    __tablename__ = "resource_allocations"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    project_slug = Column(String, nullable=False, index=True)
    linked_task_id = Column(Integer, nullable=True)  # id only — task lives in the project's own DB
    allocation_percent = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DocumentTemplate(MasterBase):
    """Global reference table (not tied to any one project). Seeded once
    from DocumentTemplateMaster_Seed.xlsx; used to auto-populate a new
    project's mandatory documents based on its project_category."""

    __tablename__ = "document_templates"

    id = Column(Integer, primary_key=True, index=True)
    doc_code = Column(Integer, unique=True, nullable=False)
    doc_name = Column(String, nullable=False)
    phase_code = Column(Integer)
    phase_name = Column(String)  # UR/DR/DN/PU/ST/UT/TR/IP/MA
    doc_set_no = Column(String)
    doc_set_name = Column(String)
    mandatory_critical = Column(String)  # M | O
    mandatory_non_critical = Column(String)  # M | O
    mandatory_ma = Column(String)  # M | O
    mandatory_rollout = Column(String)  # M | O
    defined_by = Column(String)
    documented_by = Column(String)
    approved_by = Column(String)


class ExternalWorkReference(MasterBase):
    """PM-owned mapping from an ecosystem source object (e.g. a Conductor
    DeliveryWorkPackage) to whatever PM Again created/reused locally in
    response to it. Deliberately separate from Project/Task rather than
    stuffing ecosystem fields onto every existing table — see
    docs/architecture/PM_CONDUCTOR_BOUNDARY.md.

    idempotency_key is unique: replaying the same source payload must map to
    the same row (CONDUCTOR_INTAKE_IDEMPOTENCY), and payload_hash lets a
    same-key-different-payload replay be detected as an explicit conflict
    (IDEMPOTENCY_CONFLICT_REJECTED) rather than silently overwritten."""

    __tablename__ = "external_work_references"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    tenant_id = Column(String, nullable=True)
    source_system = Column(String, nullable=False)  # e.g. CONDUCTOR_MAIN
    source_object_type = Column(String, nullable=False)  # e.g. DELIVERY_WORK_PACKAGE
    source_object_id = Column(String, nullable=False)
    correlation_id = Column(String, nullable=False, index=True)
    idempotency_key = Column(String, unique=True, nullable=False, index=True)
    payload_hash = Column(String, nullable=False)
    local_object_type = Column(String, nullable=True)  # e.g. project | task
    local_object_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="RECEIVED")  # RECEIVED|MAPPED|ACTIVE|BLOCKED|COMPLETED|CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvidenceReference(MasterBase):
    """A link to operational evidence, not a copy of it — PM Again stores
    where evidence lives (and a short summary), never the raw specialist
    payload (see EVIDENCE_REFERENCE_MODEL in the ecosystem integration
    plan)."""

    __tablename__ = "evidence_references"

    id = Column(Integer, primary_key=True, index=True)
    external_work_reference_id = Column(Integer, ForeignKey("external_work_references.id"), nullable=False)
    type = Column(String, nullable=True)
    source = Column(String, nullable=True)
    reference = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Function(ProjectBase):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, index=True)
    function_code = Column(String)
    name = Column(String, nullable=False)
    description = Column(Text)
    type = Column(String)  # Functional / Non-Functional
    phase = Column(String)  # UR/DR/DN/PU/ST/UT/TR/IP/MA
    owner = Column(String)
    status = Column(String, default="Draft")  # Draft/Confirmed/InProgress/Done

    # Extension fields (nullable) — used when the owning project's
    # project_type is "estimate"; left NULL for "simple" projects.
    module = Column(String, nullable=True)
    priority = Column(String, nullable=True)  # Must/Should/Could/Won't (MoSCoW)
    scope_class = Column(String, nullable=True)  # Core / Core-Overlap / Extended
    complexity = Column(String, nullable=True)  # Low/Medium/High
    pd_ba = Column(Float, nullable=True)
    pd_ux = Column(Float, nullable=True)
    pd_fe = Column(Float, nullable=True)
    pd_be = Column(Float, nullable=True)
    pd_int_data = Column(Float, nullable=True)
    pd_qa = Column(Float, nullable=True)
    pd_devops = Column(Float, nullable=True)
    pd_total = Column(Float, nullable=True)  # server-computed sum of pd_*
    performance_class = Column(String, nullable=True)
    target_option_a = Column(String, nullable=True)
    target_option_b = Column(String, nullable=True)
    target_option_c = Column(String, nullable=True)
    performance_note = Column(Text, nullable=True)
    price_thb = Column(Float, nullable=True)
    commercial_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(ProjectBase):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_code = Column(String)
    title = Column(String, nullable=False)
    description = Column(Text)
    phase = Column(String, nullable=True)  # UR/DR/DN/PU/ST/UT/TR/IP/MA
    owner = Column(String)
    due_date = Column(Date)
    status = Column(String, default="Todo")  # Todo/InProgress/Done/Blocked
    priority = Column(String, default="Med")  # Low/Med/High
    is_followup = Column(Boolean, default=False)
    linked_function_id = Column(Integer, ForeignKey("functions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GanttItem(ProjectBase):
    __tablename__ = "gantt_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phase = Column(String, nullable=True)  # UR/DR/DN/PU/ST/UT/TR/IP/MA
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    progress = Column(Integer, default=0)
    dependencies = Column(String)  # comma-separated gantt_item ids
    # The original Task-only link. Still the column the Gantt bar chart reads
    # and writes — deliberately left untouched by the Progress Matrix work so
    # that view keeps behaving exactly as before.
    linked_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    # Generalised link, added for the Progress Matrix (Yotei-Jisseki): lets a
    # Function / Board Item own a gantt_items row purely to carry its
    # baseline_start/baseline_end, without needing a Task. Backfilled from
    # linked_task_id for every pre-existing row (see backfill_gantt_entity_links).
    linked_entity_type = Column(String, nullable=True)  # task | function | board_item
    linked_entity_id = Column(Integer, nullable=True)
    is_milestone = Column(Boolean, default=False)
    baseline_start = Column(Date, nullable=True)
    baseline_end = Column(Date, nullable=True)
    google_calendar_event_id = Column(String, nullable=True)  # reserved — no OAuth flow yet


class GanttAnnotation(ProjectBase):
    __tablename__ = "gantt_annotations"

    id = Column(Integer, primary_key=True, index=True)
    gantt_date = Column(Date, nullable=False)
    content = Column(Text, nullable=False)
    linked_gantt_item_id = Column(Integer, ForeignKey("gantt_items.id"), nullable=True)
    color = Column(String, default="yellow")  # freeform category tag e.g. yellow/red/blue
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Document(ProjectBase):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    doc_code = Column(String)  # e.g. URS-001
    title = Column(String, nullable=False)
    phase = Column(String)  # UR/DR/DN/PU/ST/UT/TR/IP/MA
    doc_type = Column(String)  # free text — varies per project
    status = Column(String, default="Draft")  # Draft/InReview/Confirmed/Rejected
    version = Column(Integer, default=1)
    owner = Column(String)
    file_path = Column(String, nullable=True)
    google_drive_file_id = Column(String, nullable=True)  # reserved — no OAuth flow yet
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentSignoff(ProjectBase):
    __tablename__ = "document_signoffs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    signed_by = Column(String, nullable=False)
    signed_role = Column(String)
    signed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, nullable=False)  # Approved / Rejected
    comment = Column(Text, nullable=True)


class Comment(ProjectBase):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)  # "task" | "document"
    entity_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(ProjectBase):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)  # "function" | "task" | "document"
    entity_id = Column(Integer, nullable=False)
    field_changed = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String, nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)


class Note(ProjectBase):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    status = Column(String, default="Open")  # Open / PromotedToTask / PromotedToIssue
    linked_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    linked_issue_id = Column(Integer, ForeignKey("board_items.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class NotePage(ProjectBase):
    """A full markdown note (Obsidian-style), distinct from `Note` above —
    `Note` is the one-line quick-capture jotting that gets promoted to a
    task/issue, whereas this is a long-lived wiki page with hashtags and
    wiki-links."""

    __tablename__ = "note_pages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content_markdown = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NoteTag(ProjectBase):
    """Derived index, not user-managed: fully rebuilt from
    note_pages.content_markdown on every save (see note_parser.resync_note)."""

    __tablename__ = "note_tags"

    id = Column(Integer, primary_key=True, index=True)
    note_page_id = Column(Integer, ForeignKey("note_pages.id"), nullable=False, index=True)
    tag = Column(String, nullable=False, index=True)  # normalized: lowercase, no leading '#'


class NoteLink(ProjectBase):
    """Derived index, same rebuild-on-save rule as NoteTag. Only *resolved*
    wiki-links get a row — an unresolved `[[...]]` is left as plain text
    rather than being an error."""

    __tablename__ = "note_links"

    id = Column(Integer, primary_key=True, index=True)
    source_note_id = Column(Integer, ForeignKey("note_pages.id"), nullable=False, index=True)
    target_type = Column(String, nullable=False)  # note | task | function | document | board_item
    target_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class BoardItem(ProjectBase):
    """Shared table for Issue / Incident / Backlog boards, distinguished by
    item_type. Lifecycle: Backlog -(promote)-> Issue -(promote)-> Incident,
    and Issue/Incident -(promote)-> Task."""

    __tablename__ = "board_items"

    id = Column(Integer, primary_key=True, index=True)
    item_type = Column(String, nullable=False)  # issue | incident | backlog
    item_code = Column(String)  # ISS-001 / INC-001 / BLG-001
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String, nullable=True)  # Low/Medium/High/Critical — nullable for backlog
    status = Column(String, nullable=False)
    phase = Column(String, nullable=True)  # UR/DR/DN/PU/ST/UT/TR/IP/MA
    owner = Column(String, nullable=True)
    linked_note_id = Column(Integer, ForeignKey("notes.id"), nullable=True)
    linked_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    promoted_from_id = Column(Integer, ForeignKey("board_items.id"), nullable=True)
    sla_due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CodeSequence(ProjectBase):
    """The running-code pointer for one entity type (task / function) in this
    project. One row per entity_type — `next_code()` reads it, advances it,
    and persists the advance in the same transaction as the entity it's
    generating a code for, so the pointer and the entity it names can't drift
    apart from a half-committed request.
    """

    __tablename__ = "code_sequences"
    __table_args__ = (UniqueConstraint("entity_type", name="uq_code_sequence_entity_type"),)

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)  # task | function
    current_alphabet = Column(String, nullable=False, default="A")
    current_number = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProgressActualOverride(ProjectBase):
    """A hand-entered RS/R for the Progress Matrix.

    Deliberately a SEPARATE table rather than columns on the entity: the
    dates derived from activity_log are evidence — they can be pointed at a
    timestamped status change and defended in front of a client. The moment a
    person can quietly edit them, they stop being evidence and become a
    negotiable figure, which is exactly the Excel behaviour this app exists to
    replace.

    So the derived value is never written to. An override sits alongside it,
    the effective value is `override ?? derived`, and where the two disagree
    the matrix says so out loud.
    """

    __tablename__ = "progress_actual_overrides"
    __table_args__ = (
        # One override row per entity — the write path upserts rather than
        # accumulating a pile of contradictory rows.
        UniqueConstraint("entity_type", "entity_id", name="uq_progress_override_entity"),
    )

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)  # task | function | board_item
    entity_id = Column(Integer, nullable=False, index=True)
    actual_start_override = Column(Date, nullable=True)
    actual_end_override = Column(Date, nullable=True)
    reason = Column(Text, nullable=True)  # why this was typed in rather than logged
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EffortEstimateConfig(ProjectBase):
    """Per-project knobs for the Function Point model. Defaults are the values
    on the customer's own spreadsheets (see effort_calculator.py); a project
    that negotiated different productivity or a different phase split changes
    them here rather than in code."""

    __tablename__ = "effort_estimate_config"

    id = Column(Integer, primary_key=True, index=True)
    productivity_screen = Column(Float, default=4.2)
    productivity_batch = Column(Float, default=4.6)
    productivity_report = Column(Float, default=4.6)
    working_days_per_month = Column(Float, default=20)
    phase_ratio_dr = Column(Float, default=0.30)
    phase_ratio_dnpu = Column(Float, default=0.40)
    phase_ratio_iftbct = Column(Float, default=0.30)
    contracted_total_md = Column(Float, nullable=True)  # man-days sold, for the Budget Gauge
    rate_thb_per_md = Column(Float, nullable=True)  # fallback when a function carries no price_thb

    # Delivery mode (HUMAN / HUMAN-in-LOOP)
    hil_leverage_json = Column(Text, nullable=True)  # per-project override of the 16-activity leverage table
    # Deliberately NOT derived from the effort reduction: how much of a saving
    # is passed on is a commercial decision, not an arithmetic consequence.
    hil_price_discount_percent = Column(Float, default=35)
    # Off by default — a client document shows the final man-days and price,
    # not how the work is produced. Turned on only for clients who have asked.
    show_delivery_mode_in_client_docs = Column(Boolean, default=False)
    # Compliance guard for contracts with data-handling clauses.
    hil_restricted = Column(Boolean, default=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EffortEstimate(ProjectBase):
    """Both the inputs and the outputs are stored deliberately: the driver
    counts so an estimate can be audited long after the fact, the calculated_*
    values so a historical number never silently changes when config does."""

    __tablename__ = "effort_estimates"

    id = Column(Integer, primary_key=True, index=True)
    linked_entity_type = Column(String, nullable=False)  # function | task | change_request
    linked_entity_id = Column(Integer, nullable=False, index=True)
    work_type = Column(String, nullable=False)  # screen | batch | report
    driver_counts_json = Column(Text, nullable=True)  # JSON blob — new drivers need no migration
    reusability_json = Column(Text, nullable=True)  # JSON blob of per-activity reuse ratios
    non_similarity_source = Column(String, default="default")  # manual | derived | default
    priority = Column(String, default="M")  # the workbook's Priority gate: non-"M" contributes 0
    complexity = Column(Float, default=1)
    non_similarity = Column(Float, default=1)

    # Delivery mode. Defaults to "human" so an estimate saved before this
    # existed keeps calculating exactly as it did (multiplier 1.0).
    delivery_mode = Column(String, default="human")  # human | human_in_loop
    # Stored rather than recomputed: if the leverage config is edited later,
    # a historical estimate can still explain the number it actually used.
    effort_multiplier_applied = Column(Float, default=1.0)
    # The HUMAN baseline, always kept whichever mode is selected, so the two
    # can be compared and the choice reversed without re-entering drivers.
    man_days_human = Column(Float, nullable=True)

    calculated_fp = Column(Float, nullable=True)
    calculated_final_fp = Column(Float, nullable=True)
    calculated_mm = Column(Float, nullable=True)
    calculated_man_days = Column(Float, nullable=True)
    md_dr = Column(Float, nullable=True)
    md_dnpu = Column(Float, nullable=True)
    md_iftbct = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChangeRequest(ProjectBase):
    __tablename__ = "change_requests"

    id = Column(Integer, primary_key=True, index=True)
    cr_code = Column(String)  # CR-001
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    requested_by = Column(String, nullable=True)
    requested_date = Column(Date, nullable=True)
    target_date = Column(Date, nullable=True)
    status = Column(String, default="Draft")  # Draft/UnderAnalysis/PendingApproval/Approved/Rejected/Deferred
    # The Impact Analysis document generated for sign-off. Approval is gated
    # on this document reaching Confirmed — see workflow_definitions.
    linked_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChangeRequestImpact(ProjectBase):
    """One CR touches many functions. linked_function_id is null for a
    function that doesn't exist yet — those are the rows that get created for
    real when the CR is approved."""

    __tablename__ = "change_request_impacts"

    id = Column(Integer, primary_key=True, index=True)
    change_request_id = Column(Integer, ForeignKey("change_requests.id"), nullable=False, index=True)
    impact_type = Column(String, nullable=False)  # new | modify | delete
    linked_function_id = Column(Integer, ForeignKey("functions.id"), nullable=True)
    function_name = Column(String, nullable=True)
    note = Column(Text, nullable=True)


class ReportGenerationLog(ProjectBase):
    __tablename__ = "report_generation_log"

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String, nullable=False)  # daily | weekly | monthly | phase_closure
    params_json = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String, nullable=True)


class Whiteboard(ProjectBase):
    __tablename__ = "whiteboards"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    xml_content = Column(Text, nullable=True)  # drawio XML
    linked_entity_type = Column(String, nullable=True)  # project|phase|function|document|task
    linked_entity_id = Column(Integer, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
