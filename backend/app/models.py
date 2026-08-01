from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint

from .database import MasterBase, ProjectBase

# QA-Again's own roles (kept from the original spec — see ADR-0001 section 2
# for why this is a global column on `users`, not a per-project table).
ROLES = ("ADMIN", "TESTER", "VIEWER")


class Project(MasterBase):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    # Optional one-way link to the matching PM-Again project — see rebuild
    # prompt section 8. No shared DB/auth/sync, just a "back to PM-Again" URL.
    external_project_url = Column(String, nullable=True)
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(MasterBase):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # ADMIN | TESTER | VIEWER
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


# ---------- Per-project QA domain models ----------
# Live in each project's own SQLite file (ProjectBase) — see database.py's
# get_project_engine. No project_id column needed, unlike the original
# spec's shared-D1 schema: the project boundary is the file itself, exactly
# PM-Again's Function/Task/GanttItem convention.

SUITE_TYPES = ("REGRESSION", "UAT", "SMOKE", "INTEGRATION", "OTHER")
REVISION_STATUSES = ("DRAFT", "PUBLISHED", "SUPERSEDED", "ARCHIVED")
REVISION_SOURCE_TYPES = ("MARKDOWN", "XLSX", "CSV", "CLONE", "MANUAL")
MUTATION_LEVELS = ("READ_ONLY", "MUTATING", "MIXED", "UNSPECIFIED")


class TestSuite(ProjectBase):
    __tablename__ = "test_suites"

    id = Column(Integer, primary_key=True, index=True)
    suite_code = Column(String, nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    suite_type = Column(String, default="OTHER")  # REGRESSION|UAT|SMOKE|INTEGRATION|OTHER
    status = Column(String, default="ACTIVE")  # ACTIVE|ARCHIVED
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScriptRevision(ProjectBase):
    """Published revisions are immutable — a correction clones into a new
    DRAFT revision (see routers/revisions.py's clone endpoint); published
    content is never edited in place."""

    __tablename__ = "script_revisions"

    id = Column(Integer, primary_key=True, index=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id"), nullable=False)
    revision_label = Column(String, nullable=False)
    revision_number_sort = Column(Integer, nullable=False)
    status = Column(String, default="DRAFT")  # DRAFT|PUBLISHED|SUPERSEDED|ARCHIVED
    change_summary = Column(Text, nullable=True)
    source_type = Column(String, default="MANUAL")  # MARKDOWN|XLSX|CSV|CLONE|MANUAL
    source_filename = Column(String, nullable=True)
    source_sha256 = Column(String, nullable=True)
    imported_at = Column(DateTime, nullable=True)
    imported_by = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    published_by = Column(String, nullable=True)
    supersedes_revision_id = Column(Integer, ForeignKey("script_revisions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("suite_id", "revision_label", name="uq_revision_suite_label"),)


class TestCase(ProjectBase):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id"), nullable=False)
    revision_id = Column(Integer, ForeignKey("script_revisions.id"), nullable=False)
    logical_case_key = Column(String, nullable=True)
    checkpoint_code = Column(String, nullable=False)
    title = Column(String, nullable=False)
    category = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    traceability_md = Column(Text, nullable=True)
    fixture_md = Column(Text, nullable=True)
    environment_md = Column(Text, nullable=True)
    setup_md = Column(Text, nullable=True)
    action_md = Column(Text, nullable=False)
    validation_md = Column(Text, nullable=True)
    expected_result_md = Column(Text, nullable=False)
    negative_path = Column(Boolean, default=False)
    mutation_level = Column(String, default="UNSPECIFIED")  # READ_ONLY|MUTATING|MIXED|UNSPECIFIED
    sequence_no = Column(Integer, default=0)
    content_sha256 = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("revision_id", "checkpoint_code", name="uq_case_revision_checkpoint"),)


class ActivityLog(ProjectBase):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    field_changed = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String, nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)
