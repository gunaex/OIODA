"""OpenTofu IaC engine implementation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .engine import IaCEngine, IaCResult, PlanInfo

TOFU_BIN = "tofu"
ALLOWED_COMMANDS = {"version", "fmt", "init", "validate", "plan", "show", "apply", "output"}


class OpenTofuEngine(IaCEngine):
    """OpenTofu IaC execution engine — subprocess-based, safe."""

    @property
    def engine_name(self) -> str:
        return "OPENTOFU"

    async def probe(self) -> str | None:
        """Return OpenTofu version or None."""
        if not shutil.which(TOFU_BIN):
            return None
        try:
            result = await self._run(["version"], cwd=None, timeout=10)
            if result.success and result.stdout:
                return result.stdout.strip().split("\n")[0]
            return None
        except Exception:
            return None

    async def fmt(self, working_dir: Path) -> IaCResult:
        # Auto-format in place (not just check)
        return await self._run(["fmt"], cwd=working_dir, timeout=30)

    async def init(self, working_dir: Path) -> IaCResult:
        return await self._run(["init", "-input=false"], cwd=working_dir, timeout=120)

    async def validate(self, working_dir: Path) -> IaCResult:
        return await self._run(["validate"], cwd=working_dir, timeout=30)

    async def plan(self, working_dir: Path, plan_path: Path) -> IaCResult:
        return await self._run(
            ["plan", "-input=false", "-out", str(plan_path)],
            cwd=working_dir, timeout=120)

    async def apply(self, working_dir: Path, plan_path: Path) -> IaCResult:
        return await self._run(
            ["apply", "-input=false", "-auto-approve", str(plan_path)],
            cwd=working_dir, timeout=300)

    async def output(self, working_dir: Path) -> dict[str, Any]:
        result = await self._run(["output", "-json"], cwd=working_dir, timeout=30)
        if result.success and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {}
        return {}

    async def show(self, plan_path: Path) -> dict[str, Any]:
        # Show needs the working directory for provider plugin schemas
        result = await self._run(["show", "-json", str(plan_path)], cwd=plan_path.parent, timeout=30)
        if result.success and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {}
        return {}

    def state_reference(self, working_dir: Path) -> str:
        return str(working_dir / "terraform.tfstate")

    async def destroy(self, working_dir: Path) -> IaCResult:
        return await self._run(
            ["apply", "-destroy", "-input=false", "-auto-approve"],
            cwd=working_dir, timeout=300)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run(
        self, args: list[str], cwd: Path | None = None, timeout: int = 60,
    ) -> IaCResult:
        cmd = args[0] if args else "unknown"
        full_args = [TOFU_BIN] + args
        start = time.monotonic()

        try:
            proc = await asyncio.create_subprocess_exec(
                *full_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
                env=self._safe_env(),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            return IaCResult(command=cmd, exit_code=-1, stderr="Timeout", duration_ms=(time.monotonic() - start) * 1000)
        except Exception as e:
            return IaCResult(command=cmd, exit_code=-1, stderr=str(e), duration_ms=(time.monotonic() - start) * 1000)
        finally:
            duration = (time.monotonic() - start) * 1000

        checksum = hashlib.sha256(stdout.encode()).hexdigest()[:16] if stdout else ""

        return IaCResult(
            command=cmd,
            exit_code=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout.strip(),
            stderr=stderr.strip(),
            checksum=checksum,
            duration_ms=duration,
        )

    def _safe_env(self) -> dict[str, str]:
        """Environment without real AWS credentials, with NO_COLOR."""
        import os
        env = os.environ.copy()
        env.pop("AWS_ACCESS_KEY_ID", None)
        env.pop("AWS_SECRET_ACCESS_KEY", None)
        env.pop("AWS_SESSION_TOKEN", None)
        env.pop("AWS_PROFILE", None)
        env.pop("AWS_DEFAULT_REGION", None)
        env["NO_COLOR"] = "1"
        env.setdefault("AWS_ENDPOINT_URL_S3", "http://localhost:4566")
        return env


def extract_plan_info(plan_json: dict[str, Any] | None) -> PlanInfo:
    """Extract resource change counts from plan JSON."""
    info = PlanInfo(raw_plan_json=plan_json)
    if not plan_json:
        return info

    changes = plan_json.get("resource_changes", [])
    info.resource_changes = changes
    for c in changes:
        actions = c.get("change", {}).get("actions", [])
        if "create" in actions:
            info.create_count += 1
        elif "update" in actions:
            info.update_count += 1
        elif "delete" in actions:
            info.delete_count += 1

    # Checksum the plan
    info.plan_checksum = hashlib.sha256(
        json.dumps(plan_json, sort_keys=True).encode()
    ).hexdigest()[:16]

    return info
