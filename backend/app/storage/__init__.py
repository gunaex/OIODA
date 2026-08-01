import os

from fastapi import HTTPException

from .base import EvidenceStorage
from .filesystem import FilesystemEvidenceStorage
from .r2 import R2EvidenceStorage
from ..database import evidence_storage_root_dir

__all__ = ["EvidenceStorage", "FilesystemEvidenceStorage", "R2EvidenceStorage", "get_evidence_storage"]


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise HTTPException(
            status_code=500,
            detail=f"STORAGE_BACKEND=r2 but {name} is not set — see docs/DEPLOYMENT.md",
        )
    return value


def get_evidence_storage() -> EvidenceStorage:
    """FastAPI dependency — swaps transparently on STORAGE_BACKEND (see
    ADR-0002). Default 'filesystem' keeps local dev zero-config, matching
    every other default in this codebase."""
    backend = os.environ.get("STORAGE_BACKEND", "filesystem").lower()
    if backend == "r2":
        return R2EvidenceStorage(
            account_id=_required_env("R2_ACCOUNT_ID"),
            bucket_name=_required_env("R2_BUCKET_NAME"),
            access_key_id=_required_env("R2_ACCESS_KEY_ID"),
            secret_access_key=_required_env("R2_SECRET_ACCESS_KEY"),
        )
    if backend != "filesystem":
        raise HTTPException(status_code=500, detail=f"Unknown STORAGE_BACKEND '{backend}' — expected 'filesystem' or 'r2'")
    return FilesystemEvidenceStorage(evidence_storage_root_dir())
