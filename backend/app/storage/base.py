from abc import ABC, abstractmethod


class EvidenceStorage(ABC):
    """Evidence binary storage, independent of where metadata lives (the
    project SQLite DB, always — see ADR-0002). Two implementations:
    FilesystemEvidenceStorage (local dev default) and R2EvidenceStorage
    (production). Routers depend only on this interface."""

    @abstractmethod
    def put(self, key: str, content: bytes, content_type: str) -> None:
        """Writes `content` under `key`. Raises on failure — callers are
        responsible for not having created a DB row yet when this is
        called, so a raised exception here never orphans a DB record."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Reads the full object back. Raises FileNotFoundError-style if
        missing — used by the filesystem-backend download path and by
        reconciliation tooling."""

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Best-effort delete — used both for the (out-of-scope-for-API)
        future purge feature and as the compensating action when a DB
        write fails after a successful put()."""

    @abstractmethod
    def presigned_get_url(
        self,
        key: str,
        expires_in: int = 300,
        response_filename: str | None = None,
        response_content_type: str | None = None,
    ) -> str | None:
        """A short-lived, credential-free download URL, or None if this
        backend doesn't support one (filesystem) — callers fall back to
        streaming bytes through the backend in that case.

        `response_filename`/`response_content_type`, when given, override
        the *response's* Content-Disposition/Content-Type for this one
        download (a presigned-URL feature — the stored object itself is
        untouched) so a browser save-as shows the evidence's real
        filename instead of its opaque non-guessable object key."""

    @abstractmethod
    def list_keys(self, prefix: str) -> list[str]:
        """Lists every key under `prefix` — used only by reconciliation
        tooling (backend/app/reconciliation.py), never by request-serving
        code. Not expected to be fast/paginated-for-scale in the MVP."""
