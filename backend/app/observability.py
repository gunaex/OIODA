"""Lightweight production observability: structured logging, request
correlation ids, and an in-process counter registry.

Deliberately avoids heavyweight monitoring infrastructure — counters are
exposed as JSON and via logs; they can be scraped by a sidecar later.
"""
from __future__ import annotations

import contextvars
import json
import logging
import threading
import time

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("da_request_id", default="-")


def set_request_id(rid: str) -> None:
    _request_id.set(rid)


def request_id() -> str:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id(),
        }
        for key in ("method", "path", "status", "duration_ms"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("app")
    root.setLevel(logging.INFO)
    if not root.handlers:
        root.addHandler(handler)
        root.propagate = False


log = logging.getLogger("app")


class Metrics:
    """Thread-safe monotonic counters keyed by name."""

    def __init__(self):
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def inc(self, name: str, delta: int = 1) -> None:
        with self._lock:
            self._counts[name] = self._counts.get(name, 0) + delta

    def set_gauge(self, name: str, value: int) -> None:
        with self._lock:
            self._counts[name] = value

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._counts)


metrics = Metrics()


def started_at() -> float:
    return _STARTED


_STARTED = time.time()
