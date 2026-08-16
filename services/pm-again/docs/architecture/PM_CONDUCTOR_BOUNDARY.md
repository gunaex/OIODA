# PM Again ↔ Conductor Main Boundary

## Canonical division of authority

```
Conductor Main = WHAT / WHY / WHEN / orchestration
PM Again       = execution visibility / project management
```

PM Again owns: `Project`, `Task`, `Milestone`/`Phase`, `Schedule`, `Assignment`, `Dependency` (within a project), `Progress`, `Issue`/`Risk`/`Blocker`, `Change Request`, `Project Activity`, `Status Reporting`, operational evidence references, and `PMStatus` generation.

PM Again does **not** own: `BusinessIntent` authority, Conductor orchestration state, the final `DeliveryReadinessResult` decision, Infrastructure state, QA acceptance authority, Account identity authority, or AI credential authority.

## What crosses the boundary

| Direction | Contract | Endpoint |
|---|---|---|
| Conductor → PM Again | `DeliveryWorkPackage` | `POST /api/ecosystem/delivery-work-packages` |
| PM Again → Conductor | `PMStatus` | `GET /api/ecosystem/pm-status?workPackageId=...` |

Both are canonical AGAIN-ECOSYSTEM v1 contracts (`contracts/v1/schemas/`), vendored verbatim into each repo and validated at the boundary — never re-declared. PM Again's authority is `DeliveryWorkPackage` *consumer* and `PMStatus` *producer*; it is not authority for `EngineeringWorkPackage`, `InfrastructureRequest`, `QARequest`, or `DeliveryReadinessResult` — those are vendored read-only for drift detection only.

## Mapping decision

`DeliveryWorkPackage.businessIntentId` → one PM `Project`, reused across every work package under that business intent. Each individual `DeliveryWorkPackage` → one seed `Task` inside that project (`backend/app/ecosystem/mapping_service.py`). This was chosen over a 1:1 work-package-to-project mapping because a single business intent typically decomposes into multiple work packages (engineering, infra, QA, pm) that should read as one project's worth of execution, not several disconnected ones.

PM Again stores only: external id, display title, execution metadata, task mapping, correlation, status reference (`ExternalWorkReference`, `EvidenceReference`). It never duplicates Conductor's orchestration engine state, full `BusinessIntent` authority, or final readiness policy.

## PMStatus is informational, not authoritative for delivery readiness

On the Conductor side, `PMStatus.projectStatus` is surfaced in `DeliveryReadinessResult.aggregatedEvidence.pmEvidence` / `specialistResults.pmStatus` (`app/orchestration/service.py::compute_readiness`), but `app/orchestration/readiness.py::evaluate_readiness()` never branches on it — `ReadinessInputs.pm_project_status` is carried through purely for evidence, by explicit design (see the comment at `readiness.py`'s `ReadinessInputs` dataclass). A `BLOCKED` PMStatus does not, by itself, force `NOT_READY` — Conductor's own readiness policy is unchanged and remains sole delivery-readiness authority.

## Correlation

`correlationId` is generated once by Conductor per delivery flow and threaded through unchanged: `DeliveryWorkPackage.correlationId` → `ExternalWorkReference.correlation_id` → `PMStatus.correlationId` → `DeliveryReadinessResult` (via `SpecialistResult.correlation_id`, validated against `run.correlation_id` in `intake_result()`).

## Idempotency

Conductor's dispatch is keyed by `Idempotency-Key: pm-{run.run_id}` (falls back to `CONDUCTOR_MAIN:DELIVERY_WORK_PACKAGE:{workPackageId}` if omitted). Same key + same payload hash → the existing `ExternalWorkReference` is returned unchanged, no duplicate project/task. Same key + a different payload hash → HTTP 409 (`app/ecosystem/intake_service.py::IdempotencyConflict`).

## What a live three-process run would additionally require

This integration was verified with PM Again's real code paths in-process (Conductor's identity simulated via dependency override — see `PM_ECOSYSTEM_INTEGRATION.md`). An actual live `conductor-again` process calling a live `pm-again` process would additionally need:

1. Both backends running (`uvicorn app.main:app --port 8000` for PM Again, Conductor's own port).
2. A real Account-Again-issued RS256 service token for `CONDUCTOR_MAIN` (via `POST /auth/service-token` against a running Account Again with a provisioned `ServiceIdentity` + client secret for that system id).
3. `PM_AGAIN_URL` set on the Conductor side and `ACCOUNT_AGAIN_URL` set on both sides pointing at the same running Account Again instance.

No code changes are needed for this — `PMAgainClient`/`require_conductor_service_identity` already implement the full live path; it simply wasn't exercised as a literal three-process run in this session.
