"""Phase 8 execution instrumentation — computed invocation counters.

Provides zero-side-effect proof that:
  - executor was not invoked for blocked requests
  - no TASK_STARTED events were emitted for blocked requests
  - no run entered EXECUTING for blocked requests
  - no target mutations occurred for blocked requests

Counters are reset between acceptance test runs.
"""

from __future__ import annotations

import threading
from typing import Any


class ExecutionInstrumentation:
    """Thread-safe counters for acceptance evidence."""

    _lock = threading.Lock()

    _executor_invocations: int = 0
    _task_started_events: int = 0
    _runs_entered_executing: int = 0
    _target_mutations: int = 0
    _real_aws_mutations: int = 0
    _production_invocations: int = 0

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._executor_invocations = 0
            cls._task_started_events = 0
            cls._runs_entered_executing = 0
            cls._target_mutations = 0
            cls._real_aws_mutations = 0
            cls._production_invocations = 0

    @classmethod
    def record_executor_invocation(cls) -> None:
        with cls._lock:
            cls._executor_invocations += 1

    @classmethod
    def record_task_started(cls) -> None:
        with cls._lock:
            cls._task_started_events += 1

    @classmethod
    def record_run_entered_executing(cls) -> None:
        with cls._lock:
            cls._runs_entered_executing += 1

    @classmethod
    def record_target_mutation(cls) -> None:
        with cls._lock:
            cls._target_mutations += 1

    @classmethod
    def record_real_aws_mutation(cls) -> None:
        with cls._lock:
            cls._real_aws_mutations += 1

    @classmethod
    def record_production_invocation(cls) -> None:
        with cls._lock:
            cls._production_invocations += 1

    @classmethod
    def snapshot(cls) -> dict[str, Any]:
        with cls._lock:
            return {
                "executorInvocations": cls._executor_invocations,
                "taskStartedEvents": cls._task_started_events,
                "runsEnteredExecuting": cls._runs_entered_executing,
                "targetMutations": cls._target_mutations,
                "realAwsMutations": cls._real_aws_mutations,
                "productionInvocations": cls._production_invocations,
            }

    @classmethod
    def evidence(cls) -> dict[str, Any]:
        """Return acceptance evidence with computed proof."""
        snap = cls.snapshot()
        return {
            **snap,
            "noExecutorInvocations": snap["executorInvocations"] == 0,
            "noTaskStartedEvents": snap["taskStartedEvents"] == 0,
            "noRunsEnteredExecuting": snap["runsEnteredExecuting"] == 0,
            "noTargetMutations": snap["targetMutations"] == 0,
            "noRealAwsMutations": snap["realAwsMutations"] == 0,
            "noProductionInvocations": snap["productionInvocations"] == 0,
        }


# Global instrumentation instance
instrumentation = ExecutionInstrumentation()
