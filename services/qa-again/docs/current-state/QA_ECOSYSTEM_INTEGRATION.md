# QA Again — Ecosystem Integration State (QA-E1–E6)

Historical baseline: `docs/current-state/QA_RUNTIME_DISCOVERY.md` (commit `f75c77f`).

```
QA_RUNTIME_CLASS_BEFORE = FUNCTIONAL_STANDALONE
QA_RUNTIME_CLASS_AFTER_E1_E3 = PARTIAL_ECOSYSTEM_INTEGRATION_READY (commit ce9ead3)
QA_RUNTIME_CLASS_AFTER_E4_E6 = ECOSYSTEM_INTEGRATION_READY_PENDING_RUNNER_AND_LIVE_GOLDEN
```

## What exists after QA-E1–E3

- `backend/app/contracts/` — vendored AGAIN-ECOSYSTEM v1/v2 canonical
  JSON Schemas plus Pydantic bindings (`v1.py`, `v2.py`), a single
  validation boundary (`validator.py`), and a drift-detection script
  (`backend/scripts/check_contract_drift.py`).
- `backend/app/ecosystem_intake.py` — idempotent QARequest intake model
  (`ExternalQARequest`) and explicit re-run vs. replay semantics
  (`QAExecutionAttempt`).
- `backend/app/qa_result_service.py` — canonical `QAResult` aggregation
  from QA Again's own runtime state (`TestCycle`, `Defect`, `SignOff`),
  reusing the existing `go_live_readiness()` blocking-defect policy rather
  than inventing new QA logic.

## What QA-E4–E6 adds

### QA-E4 — Conductor → QARequest → QA Again

- `backend/app/ecosystem/mapping_service.py` maps an inbound canonical
  `QARequest.workPackageId` onto one QA project (`ExternalQAProjectLink`,
  create-or-reuse — mirrors PM Again's `businessIntentId → project`
  link), then that project's most recently `PUBLISHED` revision (any
  suite) onto a new `TestCycle`. If the project has no published revision
  yet, the `ExternalQARequest` is recorded (`RECEIVED`) but left unmapped
  — QA Again never fabricates test cases to fill the gap.
- `POST /api/ecosystem/qa-requests` (`backend/app/routers/ecosystem_intake.py`)
  is the single service-authenticated intake boundary: canonical schema
  validation, `require_conductor_service_identity`, idempotency (409 on a
  conflicting replay), tenant context via `X-Tenant-Id`.

### QA-E5 — QAResult → Conductor

- `GET /api/ecosystem/qa-requests/{qaRequestId}/qa-result` — service-
  authenticated canonical `QAResult` lookup keyed by the identifier
  Conductor actually holds. Delegates entirely to the QA-E3
  `QAResultService`; this router adds no QA logic of its own.
- Conductor side: `CONDUCTOR-AGAIN/backend/app/integration/qa_again_client.py`
  (HTTP client) and `.../app/orchestration/dispatch/qa_adapter.py`
  (`STATUS = REAL_RUNTIME`) replace the former `HARNESS`/`ContractQAStub`
  as the default path. `dispatch-qa` now only sends the request and
  records the dispatch — QA execution is genuinely asynchronous, unlike
  the old synchronous harness — and a new `refresh-qa-result` endpoint
  polls for the real result. The old harness (`run_harness`) is preserved
  unused, for explicit local/offline fallback only.
- Conductor's existing `evaluate_readiness()` policy
  (`orchestration/readiness.py`) needed **no changes** — it already
  treats `REJECTED` as blocking, `PENDING` as not-approved, and requires
  `APPROVED` alongside engineering/infrastructure gates rather than as
  sole authority. This was verified, not assumed.

### QA-E6 — Account Again / tenant / service identity

- `backend/app/ecosystem/account_again_client.py` — QA Again's client to
  Account Again: verifies inbound `CONDUCTOR_MAIN` service tokens via
  live RS256/JWKS (`verify_service_token`), obtains QA Again's own
  outbound service token, and evaluates `QA_AGAIN` product entitlement.
  Mirrors PM Again's `app/ecosystem/account_again_client.py` structure
  exactly — same issuer/audience constants, same fail-closed behavior.
- `backend/app/ecosystem/service_auth.py` — `require_conductor_service_identity`,
  the sole dependency trusted to authorize `/api/ecosystem/qa-requests`.
  A missing token is 401; an invalid or wrong-system (`systemId !=
  CONDUCTOR_MAIN`) token is 403, even if genuinely Account-Again-signed
  (spoof-blocked — verified live in `tests/test_live_service_auth.py`
  using QA Again's own valid token presented as if it were Conductor's).
- `backend/app/ecosystem/ecosystem_auth.py` — `require_ecosystem_identity`
  / `require_project_tenant_match`. `ECOSYSTEM_MODE=true` makes Account
  Again authoritative for tenant/entitlement; local JWT auth
  (`app/auth.py`) remains for human session identity only, unchanged and
  demoted (`LOCAL_AUTH_NOT_AUTHORITATIVE_IN_ECOSYSTEM_MODE`). Applied to
  `projects.py` (single-project GET), `qa_result.py`, and `evidence.py` —
  the project/QAResult/evidence access paths, not every route.
- `Project.tenant_id` and `User.tenant_id` (nullable, additive columns) —
  a project with no `tenant_id` is exempt from tenant enforcement.

## Operational note: reactivating QA_AGAIN's service identity

QA Again's `ServiceIdentity` row in the live `ACCOUNT-AGAIN/account_again.db`
was `REVOKED` (left over from prior negative-path testing elsewhere) with
no unrevoke API — only `POST /service-identities/{id}/revoke` exists, not
its inverse. With explicit user confirmation, this was fixed with a direct
`UPDATE service_identities SET status='ACTIVE', revoked_at=NULL WHERE
system_id='QA_AGAIN'` against the running dev database (not a source
change), followed by `POST /service-identities/{id}/rotate-client-secret`
via the existing API to obtain a fresh plaintext secret, stored only in
`backend/.env` (gitignored, never committed).

## Deliberately unchanged / out of scope this pass

- QA-E7 (runner trust hardening), QA-E8 (operator UI), QA-E9 (golden
  flow), QA-E10 (live distributed closure) — not started.
- Account Again: no source changes.
- PM Again, Infrastructure Again, Local AI Control Center: untouched.
- `evaluate_readiness()` in Conductor: unchanged (verified sufficient).
