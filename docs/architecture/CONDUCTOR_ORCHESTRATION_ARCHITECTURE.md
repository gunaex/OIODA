# Conductor Main — Orchestration Architecture (E8)

## Layers

```
app/contracts/                 Canonical AGAIN-ECOSYSTEM contract bindings (E8-A)
  vendored/                    Vendored JSON Schemas + manifest.json (source commit recorded)
  validator.py                 CanonicalContractValidator — single validation boundary
  v1.py, v2.py, base.py        Pydantic bindings (CanonicalModel.validate_canonical())

app/orchestration/              Conductor's own domain (E8-B, E8-F)
  models.py                    OrchestrationBusinessIntent, DeliveryRun,
                                SpecialistDispatch, SpecialistResult, ReadinessDecision
  state_machine.py             Deterministic BusinessIntent / DeliveryRun stage transitions
  service.py                   OrchestrationService — the actual orchestration engine
  readiness.py                 Delivery Readiness policy (explicit, reason-coded)
  ecosystem_auth.py             require_ecosystem_identity — tenant + Account Again entitlement gate
  dispatch/                    Specialist adapters (E8-E), each with a disclosed AdapterStatus
    idea_to_code_adapter.py    REAL_RUNTIME
    infra_adapter.py           FROZEN_RUNTIME (reference, not live invocation)
    qa_adapter.py               HARNESS (ContractQAStub)
    pm_adapter.py               UNAVAILABLE

app/integration/
  account_again_client.py      E8-C — sole HTTP boundary to Account Again
  lacc_client.py                E8-D — sole HTTP boundary to Local AI Control Center
  adapters.py                   Pre-existing PM/QA stub HTTP calls (unchanged, legacy)

app/routers/orchestration.py    E8-G — operator API (intents, runs, dispatch, readiness)
frontend/.../OrchestrationPage.jsx   E8-G — minimal live-backed operator UI tab
```

## Data flow (golden allow path)

```
POST /api/orchestration/intents
  → OrchestrationService.create_business_intent()
  → validates v1.BusinessIntent against the canonical schema
  → persists OrchestrationBusinessIntent (tenant-scoped)

POST /api/orchestration/intents/{id}/runs
  → OrchestrationService.create_delivery_run()
  → validates v1.DeliveryWorkPackage
  → persists DeliveryRun (stage=PLAN)

POST /api/orchestration/runs/{id}/dispatch-engineering
  → idea_to_code_adapter.build_engineering_work_package()  (v1.EngineeringWorkPackage)
  → OrchestrationService.register_dispatch()  (idempotency-keyed)
  → LocalAIControlCenterClient.dispatch_engineering_work_package()
      → REAL POST to LACC's /api/integration/v1/work-packages
  → stage advances to ENGINEERING

POST /api/orchestration/runs/{id}/execute-engineering
  → LocalAIControlCenterClient.start_engineering_run()  (real plan/execute/verify via Ollama)
  → idea_to_code_adapter.to_canonical_engineering_result()  (v1.EngineeringResult)
  → OrchestrationService.intake_result()  (correlation/work-package match enforced)

POST /api/orchestration/runs/{id}/dispatch-infrastructure
  → OrchestrationService.assert_no_downstream_after_hard_failure()  (§23 hard-failure rule)
  → infra_adapter.build_infrastructure_request() / simulate_result()  (FROZEN_RUNTIME_REFERENCE)

POST /api/orchestration/runs/{id}/dispatch-qa
  → qa_adapter.build_qa_request() / run_harness()  (HARNESS, deterministic from EngineeringResult)

POST /api/orchestration/runs/{id}/readiness
  → OrchestrationService.compute_readiness()
  → readiness.evaluate_readiness()  (explicit policy, stable reason codes)
  → validates v1.DeliveryReadinessResult
```

Every step above validates its payload against the vendored canonical JSON Schema
before persisting or dispatching — there is no path that skips
`CanonicalContractValidator`.

## Tenant isolation

Every `OrchestrationBusinessIntent` / `DeliveryRun` / `SpecialistDispatch` /
`SpecialistResult` / `ReadinessDecision` row carries `tenant_id`. The API layer never
filters silently by tenant — `_get_intent_or_404` / `_get_run_or_404` return 404 (not a
filtered empty list) when the resolved tenant does not own the resource, and
`OrchestrationService.require_tenant()` raises `TenantMismatchError` at the domain
layer. `require_ecosystem_identity` resolves the tenant from `X-Tenant-Id` (defaulting
to `local-tenant` for the pre-E8 legacy-auth path) and, in `ECOSYSTEM_MODE=true`, gates
every request on a real Account Again `CONDUCTOR_MAIN` product-entitlement `ALLOW`.

## Idempotency

`SpecialistDispatch.idempotency_key` has a unique DB constraint.
`OrchestrationService.register_dispatch()` compares the caller-supplied REQUEST
fingerprint (not the rendered canonical envelope, which always carries a fresh
generated id/timestamp) against any existing row for the same key: identical
fingerprint → returns the existing dispatch (no duplicate); different fingerprint →
`IdempotencyConflictError` → HTTP 409.

## Hard-failure rule

`OrchestrationService.assert_no_downstream_after_hard_failure()` is called before every
downstream dispatch (Infrastructure, QA) and raises if the relevant upstream specialist
result is `FAILED`. The readiness engine independently enforces the same rule
(`BLOCKED_ENGINEERING_FAILED` / `BLOCKED_INFRA_FAILED`) so a caller cannot route around
it by skipping straight to `/readiness`.
