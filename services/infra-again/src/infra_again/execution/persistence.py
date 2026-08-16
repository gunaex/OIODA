"""Phase 7 Execution Persistence — SQLite storage for execution packages, runs, events, evidence."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any


class ExecutionPersistence:
    """Persist execution packages, runs, events, evidence, and results."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or os.environ.get("INFRA_AGAIN_DB", ".ai/infra-again.db")

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def initialize(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS exec_packages (
                    execution_package_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    plan_revision INTEGER NOT NULL,
                    plan_checksum TEXT NOT NULL,
                    design_id TEXT NOT NULL,
                    design_revision INTEGER NOT NULL,
                    correlation_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'DRAFT',
                    target_json TEXT NOT NULL DEFAULT '{}',
                    tasks_json TEXT NOT NULL DEFAULT '[]',
                    preflight_json TEXT NOT NULL DEFAULT '[]',
                    policy_json TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    execution_checksum TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS exec_runs (
                    run_id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PLANNED',
                    started_at TEXT,
                    completed_at TEXT,
                    summary_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS exec_events (
                    event_id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    task_id TEXT DEFAULT '',
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS exec_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    checksum TEXT DEFAULT '',
                    path_ref TEXT DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_exec_packages_plan ON exec_packages(plan_id);
                CREATE INDEX IF NOT EXISTS idx_exec_runs_package ON exec_runs(package_id);
                CREATE INDEX IF NOT EXISTS idx_exec_events_package ON exec_events(package_id);
                CREATE INDEX IF NOT EXISTS idx_exec_evidence_run ON exec_evidence(run_id);
            """)

    def persist_package(self, package: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO exec_packages
                (execution_package_id, plan_id, plan_revision, plan_checksum,
                 design_id, design_revision, correlation_id, status, target_json,
                 tasks_json, preflight_json, policy_json, created_at, updated_at, execution_checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                package["executionPackageId"], package["planId"], package["planRevision"],
                package["planChecksum"], package["designId"], package["designRevision"],
                package["correlationId"], package["status"],
                json.dumps(package.get("target", {})),
                json.dumps(package.get("tasks", [])),
                json.dumps(package.get("preflightChecks", [])),
                json.dumps(package.get("policyDecision")),
                package.get("createdAt", ""), package.get("updatedAt", ""),
                package.get("executionChecksum", ""),
            ))

    def load_package(self, package_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM exec_packages WHERE execution_package_id = ?", (package_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["target"] = json.loads(d.pop("target_json", "{}"))
            d["tasks"] = json.loads(d.pop("tasks_json", "[]"))
            d["preflightChecks"] = json.loads(d.pop("preflight_json", "[]"))
            d["policyDecision"] = json.loads(d.pop("policy_json", "null"))
            # CamelCase keys
            result = {
                "executionPackageId": d["execution_package_id"],
                "planId": d["plan_id"],
                "planRevision": d["plan_revision"],
                "planChecksum": d["plan_checksum"],
                "designId": d["design_id"],
                "designRevision": d["design_revision"],
                "correlationId": d["correlation_id"],
                "status": d["status"],
                "target": d["target"],
                "tasks": d["tasks"],
                "preflightChecks": d["preflightChecks"],
                "policyDecision": d["policyDecision"],
                "createdAt": d["created_at"],
                "updatedAt": d["updated_at"],
                "executionChecksum": d["execution_checksum"],
            }
            return result

    def persist_run(self, run: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO exec_runs (run_id, package_id, status, started_at, completed_at, summary_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                run["runId"], run["packageId"], run["status"],
                run.get("startedAt", ""), run.get("completedAt", ""),
                json.dumps(run.get("summary", {})),
            ))

    def load_run(self, run_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM exec_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            return {
                "runId": d["run_id"],
                "packageId": d["package_id"],
                "status": d["status"],
                "startedAt": d["started_at"],
                "completedAt": d["completed_at"],
                "summary": json.loads(d["summary_json"]),
            }

    def persist_event(self, event: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO exec_events (event_id, package_id, task_id, event_type, timestamp, data_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                event["eventId"], event["packageId"], event.get("taskId", ""),
                event["eventType"], event["timestamp"], json.dumps(event.get("data", {})),
            ))

    def load_events(self, package_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM exec_events WHERE package_id = ? ORDER BY timestamp",
                (package_id,)
            ).fetchall()
            return [{
                "eventId": r["event_id"], "packageId": r["package_id"],
                "taskId": r["task_id"], "eventType": r["event_type"],
                "timestamp": r["timestamp"], "data": json.loads(r["data_json"]),
            } for r in rows]

    def persist_evidence(self, evidence: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO exec_evidence
                (evidence_id, run_id, evidence_type, source, captured_at, checksum, path_ref, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evidence["evidenceId"], evidence["runId"], evidence["evidenceType"],
                evidence["source"], evidence["capturedAt"],
                evidence.get("checksum", ""), evidence.get("pathRef", ""),
                json.dumps(evidence.get("metadata", {})),
            ))

    def load_evidence(self, run_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM exec_evidence WHERE run_id = ?", (run_id,)
            ).fetchall()
            return [{
                "evidenceId": r["evidence_id"], "runId": r["run_id"],
                "evidenceType": r["evidence_type"], "source": r["source"],
                "capturedAt": r["captured_at"], "checksum": r["checksum"],
                "pathRef": r["path_ref"], "metadata": json.loads(r["metadata_json"]),
            } for r in rows]
