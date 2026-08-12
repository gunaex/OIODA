# CONDUCTOR MAIN E8 — CORE ORCHESTRATION FOUNDATION

> **Phase**: E8 — Conductor Core Orchestration Foundation + Ecosystem Integration
> **Date**: 2026-08-12
> **Builds on**: [E7_CONDUCTOR_RUNTIME_DISCOVERY.md](E7_CONDUCTOR_RUNTIME_DISCOVERY.md)

## What changed

Conductor went from `CONDUCTOR_RUNTIME_CLASS=PROTOTYPE` (zero canonical contracts, no
orchestration engine, direct AI provider calls, local-only auth) to a real orchestration
runtime with:

- All 11 v1 + 7 v2 canonical AGAIN-ECOSYSTEM contracts vendored, bound (Pydantic), and
  validated (jsonschema) at a single boundary (`app/contracts/`).
- A real domain layer (`app/orchestration/`): `BusinessIntent` → `DeliveryRun` →
  specialist dispatch → `DeliveryReadinessResult`, with an explicit deterministic
  readiness policy, a hard-failure short-circuit, and idempotent dispatch.
- A real, live-verified `AccountAgainClient` (E5.1 service-token auth, tenant/product
  entitlement) and `LocalAIControlCenterClient` (real Idea → Code dispatch boundary).
- Four specialist dispatch adapters, each with an honestly disclosed runtime
  classification: Idea → Code = `REAL_RUNTIME`, Infrastructure Again =
  `FROZEN_RUNTIME_REFERENCE`, QA Again = `HARNESS`, PM Again = `UNAVAILABLE`.
- A minimal operator UI tab (`OrchestrationPage.jsx`) backed entirely by the live API.
- A live golden allow/deny/idempotency/tenant-isolation flow, run against the actual
  running Account Again + Local AI Control Center instances on this machine.

## What did NOT change

- The existing React/FastAPI shell, dual-DB pattern, multi-agent deliberation engine,
  skill registry, and AI resource pool UI are untouched and still pass all pre-existing
  tests.
- INFRA-AGAIN was not modified (read-only classification only: `FROZEN_RUNTIME_REFERENCE`).
- PM Again and QA Again products were not built.

## Real bugs found and fixed along the way (not new E8 features)

1. **Test DB isolation bug** (`tests/conftest.py`): `DATA_DIR` was set via
   `os.environ[...]` *after* `app.database` had already been imported, so the
   module-level `DATA_DIR = os.getenv(...)` constant silently captured the default
   `./data` — every pytest run was writing real Vision/Requirement/Project rows into
   `backend/data/` instead of an isolated temp directory. This masked itself because a
   second bug (below) usually aborted those tests before their assertions ran. Fixed by
   moving the env-var assignment before the first `app.*` import; `backend/data/`
   (gitignored, non-canonical dev-run artifacts, confirmed distinct from the real
   `/data/` directory referenced in the E7 report) was deleted and now regenerates
   clean.
2. **Login rate-limit test exhaustion**: `slowapi`'s 10/minute limit on `/api/auth/login`
   is keyed by remote address; `TestClient` shares one address across an entire pytest
   session, so the limit exhausted after ~10 tests and every subsequent test using the
   `admin_token` fixture failed with `KeyError: 'access_token'` (E7 had already flagged
   this: "32 errors... rate-limit exhaustion in test fixtures, not functional bugs").
   Fixed by disabling the limiter when `TESTING=true` (set once, in `conftest.py`,
   before the app is imported) — production/dev behavior is unaffected.
3. **Stale test assertion** (`test_integration_services`): asserted the old
   `pm-again.vercel.app` placeholder URL against the real, current
   `pmagain.kanphong.com` seed value (exact E7-documented failure). Fixed the
   assertion, not the seed data.
4. Two standalone `requests`-based manual smoke scripts (`smoke_test.py`,
   `test_multi_ai.py`) execute HTTP calls at *module import time* against a live
   server — they were crashing pytest *collection*, not failing as tests. Excluded from
   collection (`collect_ignore` + `pytest.ini` `testpaths=tests`) rather than rewritten,
   since they are intentionally manual scripts. `test_multi_ai_direct.py` had an
   additional hardcoded Windows path (`d:/git/...`); guarded under `if __name__ ==
   "__main__"` and fixed the path.

Backend test suite: **117 passed, 0 failed, 0 errors** (was 36 passed / 1 failed / 32
errors under E7). The single E7-documented failure is now fixed (item 3); no new
failures were introduced.

## Known, disclosed limitation: LACC has no generic AI execution endpoint

Local AI Control Center's real, live-verified boundary for Conductor is the Idea → Code
work-package endpoint (`POST /api/integration/v1/work-packages`) — genuinely
`REAL_RUNTIME`, proven by live dispatch in this phase (see E8_H section of the final
report). It does **not** expose a generic `AIExecutionRequest` execution endpoint for a
Specialist OS's own general-reasoning needs; LACC's own `contract-conformance-v2` route
independently reports this same gap
(`AI_EXECUTION_REQUEST_LIVE=NOT_APPLICABLE_NO_RUNTIME_PRODUCER`). Per task policy
(prefer Conductor-side adaptation, don't expand LACC's surface as a side effect),
`LocalAIControlCenterClient.execute_capability()` fails closed to `BLOCKED_BY_POLICY`
rather than fabricating a call — and never falls back to a direct provider SDK call.

This means Conductor's **pre-existing** deliberation engine, skill AUTO-router,
multi-AI panel, and golden-flow decomposition (all reused, per E7's recommendation,
`REUSE_AS_IS`) still call AI providers directly via `app/adapters/*.py` — they were
**not** migrated to LACC in E8, because there is currently no real LACC endpoint to
migrate them to without expanding LACC's own scope. The **new** E8 orchestration
runtime (`app/orchestration/`, `app/routers/orchestration.py`) has zero direct provider
call sites — verified by grep in the final report's `DIRECT_PROVIDER_SCAN`. This is a
disclosed, real gap, not a hidden one; see `CONDUCTOR_SPECIALIST_BOUNDARIES.md` for the
full classification.

See the E8 final report (returned at the end of this phase) for the complete
gate-by-gate status.
