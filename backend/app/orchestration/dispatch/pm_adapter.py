"""
PM Again dispatch adapter (E8-E §43).

Classification: UNAVAILABLE. PM Again has no running local instance (E7
finding: STUB_ONLY, no canonical PMStatus contract in use). Per §43, Conductor
creates the adapter interface and consumes/produces PMStatus, but does NOT
build project-management features inside Conductor to compensate. The golden
flow marks PM as NOT_USED rather than fabricating a PMStatus (§73 explicitly
allows this).
"""

from app.orchestration.dispatch import UNAVAILABLE

STATUS = UNAVAILABLE


def health() -> bool:
    return False


def build_pm_status_placeholder(*, run) -> None:
    """No PMStatus is produced when PM Again is UNAVAILABLE — returning None (not a
    fabricated PMStatus) is the honest behavior; callers must treat PM as NOT_USED."""
    return None
