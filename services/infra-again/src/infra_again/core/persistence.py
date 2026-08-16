"""
SQLite persistence for INFRA-AGAIN.

Lightweight persistence for execution state, plans, evidence, and
resource ownership. SQLite is INFRA-AGAIN application state — NOT IaC state.
OpenTofu/Terraform remains authoritative for its own state.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.domain import (
    ExecutionMode,
    ExecutionState,
    ExecutionTarget,
    ExecutionTargetType,
    InfrastructurePlan,
    OwnedResource,
    Platform,
    Provider,
    ResourceOwnership,
    TargetScope,
    can_transition,
    VALID_TRANSITIONS,
)


DEFAULT_DB_PATH = ".ai/infra-again.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(obj: Any) -> str:
    if hasattr(obj, "model_dump"):
        return obj.model_dump_json()
    if isinstance(obj, dict):
        return json.dumps(obj, default=str)
    if hasattr(obj, "__dict__"):
        return json.dumps({k: v for k, v in obj.__dict__.items() if not k.startswith("_")}, default=str)
    return json.dumps(obj, default=str)


class RunStore:
    """SQLite-backed execution run store."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    correlation_id TEXT NOT NULL,
                    work_package_id TEXT,
                    infrastructure_request_id TEXT,
                    idempotency_key TEXT,
                    state TEXT NOT NULL DEFAULT 'DRAFT',
                    provider TEXT,
                    platform TEXT,
                    execution_mode TEXT,
                    execution_target_type TEXT,
                    execution_target_endpoint TEXT,
                    iac_engine TEXT,
                    iac_version TEXT,
                    iac_stage TEXT NOT NULL DEFAULT 'NOT_STARTED',
                    iac_checksum TEXT,
                    iac_plan_checksum TEXT,
                    iac_plan_sha256 TEXT,
                    iac_approved_plan_sha256 TEXT,
                    iac_applied_plan_sha256 TEXT,
                    iac_plan_artifact_path TEXT,
                    iac_state_reference TEXT,
                    iac_working_dir TEXT,
                    request_json TEXT,
                    normalized_intent TEXT,
                    plan TEXT,
                    policy_decision TEXT,
                    approval_state TEXT,
                    error TEXT,
                    final_result TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runs_correlation ON runs(correlation_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_idempotency ON runs(idempotency_key)
                    WHERE idempotency_key IS NOT NULL;

                CREATE TABLE IF NOT EXISTS state_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    reason TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS resources (
                    resource_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    managed_by TEXT NOT NULL DEFAULT 'INFRA_AGAIN',
                    created_by_run_id TEXT NOT NULL,
                    ephemeral INTEGER NOT NULL DEFAULT 1,
                    target_scope TEXT NOT NULL DEFAULT 'ISOLATED',
                    state TEXT,
                    observed_state TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS evidence_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    reference TEXT NOT NULL,
                    summary TEXT,
                    data TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS apply_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    request_data TEXT,
                    response_data TEXT,
                    error_data TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
            """)

    # ------------------------------------------------------------------
    # Run CRUD
    # ------------------------------------------------------------------

    def create_run(
        self,
        run_id: str,
        correlation_id: str,
        work_package_id: str = "",
        infrastructure_request_id: str = "",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        now = _now()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO runs (run_id, correlation_id, work_package_id,
                   infrastructure_request_id, idempotency_key, state, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, correlation_id, work_package_id, infrastructure_request_id,
                 idempotency_key, ExecutionState.DRAFT.value, now, now),
            )
        return self.get_run(run_id) or {}

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            return dict(row)

    def get_run_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if row is None:
                return None
            return dict(row)

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_run(run_id)
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [run_id]
        with self._get_conn() as conn:
            conn.execute(f"UPDATE runs SET {set_clause} WHERE run_id = ?", values)
        return self.get_run(run_id)

    def list_runs(self, correlation_id: str | None = None) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            if correlation_id:
                rows = conn.execute(
                    "SELECT * FROM runs WHERE correlation_id = ? ORDER BY created_at DESC",
                    (correlation_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def transition_state(
        self,
        run_id: str,
        to_state: ExecutionState,
        reason: str = "",
    ) -> tuple[bool, str]:
        """Attempt a state transition. Returns (success, message)."""
        run = self.get_run(run_id)
        if run is None:
            return False, f"Run {run_id} not found"

        from_state = ExecutionState(run["state"])

        if not can_transition(from_state, to_state):
            return False, (
                f"Illegal transition: {from_state.value} → {to_state.value}. "
                f"Valid targets: {[s.value for s in VALID_TRANSITIONS.get(from_state, set())]}"
            )

        with self._get_conn() as conn:
            conn.execute(
                "UPDATE runs SET state = ?, updated_at = ? WHERE run_id = ?",
                (to_state.value, _now(), run_id),
            )
            conn.execute(
                "INSERT INTO state_transitions (run_id, from_state, to_state, reason, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, from_state.value, to_state.value, reason, _now()),
            )
        return True, f"Transitioned: {from_state.value} → {to_state.value}"

    def get_transitions(self, run_id: str) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM state_transitions WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Resource ownership
    # ------------------------------------------------------------------

    def register_resource(self, resource: OwnedResource) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO resources
                   (resource_id, run_id, resource_type, provider, managed_by,
                    created_by_run_id, ephemeral, target_scope, state, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    resource.resource_id,
                    resource.ownership.created_by_run_id,
                    resource.resource_type,
                    resource.provider,
                    resource.ownership.managed_by,
                    resource.ownership.created_by_run_id,
                    1 if resource.ownership.ephemeral else 0,
                    resource.ownership.target_scope.value,
                    _serialize(resource.state),
                    resource.created_at.isoformat(),
                ),
            )

    def get_resource(self, resource_id: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM resources WHERE resource_id = ?", (resource_id,)
            ).fetchone()
            if row is None:
                return None
            return dict(row)

    def get_resources_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM resources WHERE run_id = ?", (run_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def update_resource_state(self, resource_id: str, state: dict[str, Any]) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE resources SET state = ? WHERE resource_id = ?",
                (_serialize(state), resource_id),
            )

    def update_resource_observed(self, resource_id: str, observed_state: dict[str, Any]) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE resources SET observed_state = ? WHERE resource_id = ?",
                (_serialize(observed_state), resource_id),
            )

    def can_auto_destroy(self, resource_id: str, current_run_id: str) -> tuple[bool, str]:
        """Check if AUTO destroy is allowed for a resource."""
        resource = self.get_resource(resource_id)
        if resource is None:
            return False, f"Resource {resource_id} not found in ownership registry"

        ownership = ResourceOwnership(
            managed_by=resource["managed_by"],
            created_by_run_id=resource["created_by_run_id"],
            ephemeral=bool(resource["ephemeral"]),
            target_scope=TargetScope(resource["target_scope"]),
        )

        if ownership.is_auto_destroy_allowed(current_run_id):
            return True, "AUTO destroy allowed: owned, ephemeral, ISOLATED, same run"

        reasons: list[str] = []
        if ownership.managed_by != "INFRA_AGAIN":
            reasons.append(f"managed_by={ownership.managed_by}")
        if ownership.created_by_run_id != current_run_id:
            reasons.append(f"created_by_run_id={ownership.created_by_run_id} != current={current_run_id}")
        if not ownership.ephemeral:
            reasons.append("not ephemeral")
        if ownership.target_scope != TargetScope.ISOLATED:
            reasons.append(f"target_scope={ownership.target_scope.value}")

        return False, f"Destroy not AUTO: {'; '.join(reasons)}"

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def add_evidence(
        self,
        run_id: str,
        evidence_type: str,
        source: str,
        reference: str,
        summary: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO evidence_items (run_id, evidence_type, source, reference, summary, data, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, evidence_type, source, reference, summary, _serialize(data or {}), _now()),
            )

    def get_evidence(self, run_id: str) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_items WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Apply log
    # ------------------------------------------------------------------

    def log_apply(
        self,
        run_id: str,
        resource_id: str,
        operation: str,
        endpoint: str,
        request_data: dict[str, Any] | None = None,
        response_data: dict[str, Any] | None = None,
        error_data: dict[str, Any] | None = None,
    ) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO apply_log (run_id, resource_id, operation, endpoint, "
                "request_data, response_data, error_data, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, resource_id, operation, endpoint,
                    _serialize(request_data or {}),
                    _serialize(response_data or {}),
                    _serialize(error_data or {}),
                    _now(),
                ),
            )

    def get_apply_logs(self, run_id: str) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM apply_log WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Final result persistence
    # ------------------------------------------------------------------

    def persist_final_result(self, run_id: str, result_json: str) -> None:
        """Persist the canonical InfrastructureResult JSON for exact retrieval."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE runs SET final_result = ?, updated_at = ? WHERE run_id = ?",
                (result_json, _now(), run_id),
            )

    def get_final_result(self, run_id: str) -> str | None:
        """Retrieve the persisted canonical InfrastructureResult."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT final_result FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None or row["final_result"] is None:
                return None
            return row["final_result"]

    # ------------------------------------------------------------------
    # Request persistence
    # ------------------------------------------------------------------

    def persist_request(self, run_id: str, request_json: str) -> None:
        """Persist the full canonical InfrastructureRequest JSON."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE runs SET request_json = ?, updated_at = ? WHERE run_id = ?",
                (request_json, _now(), run_id),
            )

    def get_request(self, run_id: str) -> str | None:
        """Retrieve the persisted canonical InfrastructureRequest JSON."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT request_json FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None or row["request_json"] is None:
                return None
            return row["request_json"]
