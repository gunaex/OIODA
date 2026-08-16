# INFRA-AGAIN State Model

## Execution States

```
DRAFT
    ↓
NORMALIZING       # Interpreting InfrastructureRequest
    ↓
PLANNING          # Generating provider plan
    ↓
PLAN_READY        # Plan complete, awaiting approval
    ↓
WAITING_FOR_APPROVAL
    ↓
APPROVED
    ↓
EXECUTING         # Applying changes
    ↓
OBSERVING         # Collecting post-execution state
    ↓
VALIDATING        # Comparing desired vs observed
    ↓
COMPLETED         # Success
```

Terminal states:
- FAILED — Execution error
- BLOCKED — Policy gate blocked
- CANCELLED — User cancelled

## Persistence

Phase 1: In-memory only (NOT IMPLEMENTED for resumable execution)
Phase 2: SQLite/file-based persistence planned

## Truthfulness

Runtime statuses must be truthful:
- NOT_CONFIGURED, NOT_INSTALLED, OFFLINE
- UNAVAILABLE, AUTH_REQUIRED, AUTH_FAILED
- UNSUPPORTED, UNVERIFIED
- BLOCKED_BY_POLICY, BLOCKED_BY_AIRLOCK
- READY
