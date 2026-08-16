#!/usr/bin/env python
"""P4-N API performance smoke — representative timings, NOT benchmarks.

Runs against the current database (fresh-migrated). Prints wall-clock
timings for the key workspace operations. Small local fixtures only; do not
read these as production numbers.
"""
from __future__ import annotations

import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def timed(name, fn):
    t0 = time.perf_counter()
    result = fn()
    dt = (time.perf_counter() - t0) * 1000
    print(f"{name:28s} {dt:8.1f} ms")
    return result


def main() -> int:
    with TestClient(app) as c:
        timed("project list", lambda: c.get("/api/projects"))
        pid = timed("create project", lambda: c.post("/api/projects", json={"key": "PERF", "name": "Perf"}).json())["id"]
        timed("requirement create", lambda: c.post("/api/requirements", json={"project_id": pid, "title": "Perf req"}))
        timed("semantic search", lambda: c.get(f"/api/projects/{pid}/search?q=req"))
        schema = timed("db schema create", lambda: c.post("/api/db-schemas", json={"project_id": pid, "name": "core", "semantic_id": "sch_core"}).json())
        tbl = timed("db table create", lambda: c.post("/api/db-tables", json={"schema_id": schema["id"], "name": "orders"}).json())
        timed("db field create", lambda: c.post("/api/db-fields", json={"table_id": tbl["id"], "name": "id", "data_type": "UUID", "primary_key": True}))
        timed("impact analysis v2", lambda: c.get(f"/api/projects/{pid}/impact-v2/REQ-0001"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
