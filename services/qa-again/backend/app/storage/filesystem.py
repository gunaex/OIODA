import os

from .base import EvidenceStorage


class FilesystemEvidenceStorage(EvidenceStorage):
    """ADR-0001's original approach — kept as the zero-config local
    development default (see ADR-0002). `root_dir` is the evidence root
    (database.py's project_evidence_dir), `key` is a relative path under
    it (e.g. `evidence/{slug}/{result_id}/{uuid}.png`)."""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def _path(self, key: str) -> str:
        return os.path.join(self.root_dir, key)

    def put(self, key: str, content: bytes, content_type: str) -> None:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)

    def get(self, key: str) -> bytes:
        with open(self._path(key), "rb") as f:
            return f.read()

    def exists(self, key: str) -> bool:
        return os.path.exists(self._path(key))

    def delete(self, key: str) -> None:
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    def presigned_get_url(
        self,
        key: str,
        expires_in: int = 300,
        response_filename: str | None = None,
        response_content_type: str | None = None,
    ) -> str | None:
        return None  # no presigned-URL concept for local files — caller streams bytes instead

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if not os.path.isdir(base):
            return []
        keys = []
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                full = os.path.join(dirpath, name)
                keys.append(os.path.relpath(full, self.root_dir).replace(os.sep, "/"))
        return keys
