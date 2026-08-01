from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    must_change_password: bool

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str
    external_project_url: Optional[str] = None


class ProjectArchiveRequest(BaseModel):
    archived: bool
    password: str


class ProjectDeleteRequest(BaseModel):
    password: str


class ProjectOut(BaseModel):
    id: int
    name: str
    slug: str
    external_project_url: Optional[str] = None
    archived: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Test suites ----------


class TestSuiteCreate(BaseModel):
    name: str
    suite_code: Optional[str] = None
    description: Optional[str] = None
    suite_type: str = "OTHER"


class TestSuiteUpdate(BaseModel):
    name: Optional[str] = None
    suite_code: Optional[str] = None
    description: Optional[str] = None
    suite_type: Optional[str] = None
    status: Optional[str] = None


class TestSuiteOut(BaseModel):
    id: int
    suite_code: Optional[str] = None
    name: str
    description: Optional[str] = None
    suite_type: str
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Script revisions ----------


class RevisionCreate(BaseModel):
    revision_label: str
    change_summary: Optional[str] = None


class RevisionPublishRequest(BaseModel):
    published_by: Optional[str] = None


class RevisionCloneRequest(BaseModel):
    revision_label: str
    change_summary: Optional[str] = None
    created_by: Optional[str] = None


class RevisionOut(BaseModel):
    id: int
    suite_id: int
    revision_label: str
    revision_number_sort: int
    status: str
    change_summary: Optional[str] = None
    source_type: str
    source_filename: Optional[str] = None
    source_sha256: Optional[str] = None
    imported_at: Optional[datetime] = None
    imported_by: Optional[str] = None
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None
    supersedes_revision_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Test cases ----------


class TestCaseCreate(BaseModel):
    checkpoint_code: str
    title: str
    logical_case_key: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    traceability_md: Optional[str] = None
    fixture_md: Optional[str] = None
    environment_md: Optional[str] = None
    setup_md: Optional[str] = None
    action_md: str
    validation_md: Optional[str] = None
    expected_result_md: str
    negative_path: bool = False
    mutation_level: str = "UNSPECIFIED"
    sequence_no: int = 0


class TestCaseUpdate(BaseModel):
    checkpoint_code: Optional[str] = None
    title: Optional[str] = None
    logical_case_key: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    traceability_md: Optional[str] = None
    fixture_md: Optional[str] = None
    environment_md: Optional[str] = None
    setup_md: Optional[str] = None
    action_md: Optional[str] = None
    validation_md: Optional[str] = None
    expected_result_md: Optional[str] = None
    negative_path: Optional[bool] = None
    mutation_level: Optional[str] = None
    sequence_no: Optional[int] = None


class TestCaseOut(BaseModel):
    id: int
    suite_id: int
    revision_id: int
    logical_case_key: Optional[str] = None
    checkpoint_code: str
    title: str
    category: Optional[str] = None
    priority: Optional[str] = None
    traceability_md: Optional[str] = None
    fixture_md: Optional[str] = None
    environment_md: Optional[str] = None
    setup_md: Optional[str] = None
    action_md: str
    validation_md: Optional[str] = None
    expected_result_md: str
    negative_path: bool
    mutation_level: str
    sequence_no: int
    content_sha256: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- HYB-0 spike ----------


class RunnerTokenCreate(BaseModel):
    label: str


class RunnerTokenOut(BaseModel):
    id: int
    label: str
    token: str  # raw token — returned once, at creation, never again


class HybridRunCreate(BaseModel):
    label: Optional[str] = None


class HybridRunOut(BaseModel):
    id: int
    status: str
    label: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HybridRunEventCreate(BaseModel):
    event_type: str
    actor_type: str
    payload_json: Optional[str] = None


class HybridRunEventOut(BaseModel):
    id: int
    run_id: int
    event_type: str
    actor_type: str
    payload_json: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HybridRunDetailOut(HybridRunOut):
    events: list[HybridRunEventOut] = []
    latest_decision: Optional["HybridCheckpointDecisionOut"] = None


class HybridCheckpointDecisionCreate(BaseModel):
    decision: str
    reason: Optional[str] = None


class HybridCheckpointDecisionOut(BaseModel):
    id: int
    run_id: int
    decision: str
    reason: Optional[str] = None
    decided_by: str
    decided_at: datetime

    class Config:
        from_attributes = True


class HybridRunEvidenceOut(BaseModel):
    id: int
    run_id: int
    original_filename: str
    original_content_type: str
    original_size_bytes: int
    original_sha256: str
    captured_at: datetime

    class Config:
        from_attributes = True


HybridRunDetailOut.model_rebuild()
