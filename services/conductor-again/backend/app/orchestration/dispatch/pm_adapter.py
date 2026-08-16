"""
PM Again dispatch adapter (E8-E §43 / PM-E5).

Classification: REAL_RUNTIME. PM Again now runs a real canonical
DeliveryWorkPackage intake endpoint and produces a real canonical PMStatus
from its own project execution state (contracts/vendored/v1/schemas/
PMStatus.json, backend/app/pm_status_service.py in the PM Again repo).

Still never fabricates: fetch_status returns None (not a synthetic
PMStatus) whenever PM Again has no mapping for a work package yet, or is
unreachable — the same "PM as NOT_USED rather than fabricating" principle
the stub always stated, just backed by a real client now instead of an
always-None placeholder.
"""

from typing import Any, Optional

from app.integration.pm_again_client import PMAgainClient
from app.orchestration.dispatch import REAL_RUNTIME

STATUS = REAL_RUNTIME


def health() -> bool:
    return PMAgainClient.health()


def dispatch(*, run, delivery_work_package: dict[str, Any]) -> dict[str, Any]:
    """Sends the canonical DeliveryWorkPackage to PM Again. Raises
    PMAgainUnavailableError on transport failure — caller decides fallback
    policy, same convention as the other REAL_RUNTIME adapters."""
    idempotency_key = f"pm-{run.run_id}"
    return PMAgainClient.dispatch_delivery_work_package(
        delivery_work_package=delivery_work_package, idempotency_key=idempotency_key, tenant_id=run.tenant_id,
    )


def fetch_status(*, run) -> Optional[dict[str, Any]]:
    """Fetches the real canonical PMStatus for this run's work package.
    Returns None — never a fabricated status — if PM Again has no mapping
    yet or can't be reached."""
    return PMAgainClient.get_pm_status(run.work_package_id)
