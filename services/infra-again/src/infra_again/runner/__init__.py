"""Infra Again Runner — Execution Plane models."""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class RunnerStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    BUSY = "BUSY"
    ERROR = "ERROR"


class TaskState(str, Enum):
    QUEUED = "QUEUED"
    LEASED = "LEASED"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REQUIRES_RECONCILIATION = "REQUIRES_RECONCILIATION"


class ToolStatus(str, Enum):
    READY = "READY"
    NOT_INSTALLED = "NOT_INSTALLED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class RunnerIdentity:
    runner_id: str = field(default_factory=lambda: f"runner-{uuid4().hex[:8]}")
    name: str = ""
    version: str = "0.1.0"
    os_name: str = ""
    arch: str = ""
    status: RunnerStatus = RunnerStatus.OFFLINE
    registered_at: str | None = None
    last_heartbeat: str | None = None
    auth_token_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "runnerId": self.runner_id, "name": self.name,
            "version": self.version, "os": self.os_name, "arch": self.arch,
            "status": self.status.value,
            "registeredAt": self.registered_at,
            "lastHeartbeat": self.last_heartbeat,
        }


@dataclass
class RunnerCapabilities:
    runner_id: str = ""
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    detected_at: str = ""

    @classmethod
    def detect(cls, runner_id: str) -> RunnerCapabilities:
        caps = RunnerCapabilities(
            runner_id=runner_id,
            detected_at=datetime.now(timezone.utc).isoformat(),
        )
        caps.tools = {
            "tofu": cls._probe_tool("tofu", ["version"]),
            "kubectl": cls._probe_tool("kubectl", ["version", "--client"]),
            "kind": cls._probe_tool("kind", ["version"]),
            "minikube": cls._probe_tool("minikube", ["version"]),
            "crc": cls._probe_tool("crc", ["version"]),
            "docker": cls._probe_tool("docker", ["version"]),
            "fakecloud": cls._probe_tool("fakecloud", ["--version"]),
        }
        return caps

    @staticmethod
    def _probe_tool(name: str, version_args: list[str]) -> dict[str, Any]:
        if not shutil.which(name):
            return {"status": ToolStatus.NOT_INSTALLED.value}
        try:
            import subprocess
            result = subprocess.run([name] + version_args, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {"status": ToolStatus.READY.value, "version": result.stdout.strip().split("\n")[0]}
        except Exception:
            pass
        return {"status": ToolStatus.UNAVAILABLE.value}

    def to_dict(self) -> dict[str, Any]:
        return {"runnerId": self.runner_id, "tools": self.tools, "detectedAt": self.detected_at}


@dataclass
class ExecutionTask:
    schema_version: str = "1.0"
    task_id: str = field(default_factory=lambda: f"task-{uuid4().hex[:8]}")
    run_id: str = ""
    correlation_id: str = ""
    execution_mode: str = ""
    provider: str = ""
    platform: str = ""
    target: str = ""
    action: str = "APPLY"
    plan_reference: str = ""
    policy_decision: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version, "taskId": self.task_id,
            "runId": self.run_id, "correlationId": self.correlation_id,
            "executionMode": self.execution_mode, "provider": self.provider,
            "platform": self.platform, "target": self.target,
            "action": self.action, "planReference": self.plan_reference,
            "policy": {"decision": self.policy_decision},
            "requiredCapabilities": self.required_capabilities,
            "createdAt": self.created_at,
        }


@dataclass
class TaskLease:
    lease_id: str = field(default_factory=lambda: f"lease-{uuid4().hex[:8]}")
    task_id: str = ""
    runner_id: str = ""
    leased_at: str = ""
    expires_at: str = ""
    state: TaskState = TaskState.LEASED

    def to_dict(self) -> dict[str, Any]:
        return {
            "leaseId": self.lease_id, "taskId": self.task_id,
            "runnerId": self.runner_id, "leasedAt": self.leased_at,
            "expiresAt": self.expires_at, "state": self.state.value,
        }

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > exp
        except Exception:
            return False


@dataclass
class ExecutionEvent:
    event_id: str = field(default_factory=lambda: f"evt-{uuid4().hex[:8]}")
    task_id: str = ""
    runner_id: str = ""
    stage: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {"eventId": self.event_id, "taskId": self.task_id,
                "runnerId": self.runner_id, "stage": self.stage,
                "data": self.data, "timestamp": self.timestamp}
