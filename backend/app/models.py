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
)

from .database import MasterBase, ProjectBase


class Project(MasterBase):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    project_type = Column(String, default="simple")  # simple | estimate
    project_category = Column(String, nullable=True)  # critical | non_critical | ma | rollout
    notification_email = Column(String, nullable=True)  # reserved for future email alerts
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


RESOURCE_ROLES = ("SR.Arc", "DevSecOps", "SEC", "DBA", "Dev", "QA", "BA", "UX", "DevOps")


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
    linked_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    is_milestone = Column(Boolean, default=False)
    baseline_start = Column(Date, nullable=True)
    baseline_end = Column(Date, nullable=True)
    google_calendar_event_id = Column(String, nullable=True)  # reserved — no OAuth flow yet


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
