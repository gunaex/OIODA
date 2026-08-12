# Conductor Main — Specialist Dispatch Boundaries (E8-E)

Truthful runtime classification per adapter, verified live against this machine's
actually-running services on 2026-08-12. Conductor is the orchestrator; it does not
perform specialist work itself in any of the four boundaries below.

## Idea → Code — `REAL_RUNTIME`

- Boundary: `LocalAIControlCenterClient.dispatch_engineering_work_package()` →
  `POST http://localhost:9191/api/integration/v1/work-packages`.
- Verified live in this phase: dispatched a real work package, ran the real pipeline
  (`start_engineering_run` → real Ollama `qwen2.5-coder:7b` plan/build/test/verify),
  and mapped the real outcome to a canonical `EngineeringResult`.
- Adapter, not shared contract: LACC's local `DeliveryWorkPackageV1` shape
  (`schemaVersion`, `goal`, `P0`-`P3` priority, etc.) is LACC's own internal contract,
  distinct field-for-field from AGAIN-ECOSYSTEM's canonical v1 `DeliveryWorkPackage`.
  `idea_to_code_adapter.py` is the explicit translation layer; LACC is not treated as a
  second contract authority.
- Disclosed gap: LACC exposes no generic `AIExecutionRequest` execution endpoint for
  Conductor's own AI reasoning needs (see `LOCAL_AI_CONTROL_CENTER_URL` client
  docstring). `execute_capability()` fails closed rather than filling that gap by
  expanding LACC's scope or falling back to a direct provider call.

## Infrastructure Again — `FROZEN_RUNTIME_REFERENCE` (not `LIVE_ADAPTER`)

- INFRA-AGAIN is frozen (`again-ecosystem-v1` / `infra-again-v1` tags) and explicitly
  out of scope to modify or invoke with real side effects for this task.
- `infra_adapter.py` builds a genuinely canonical, schema-valid `InfrastructureRequest`
  from real upstream data (the actual `EngineeringResult`), but
  `simulate_result()` returns a disclosed, deterministic simulated
  `InfrastructureResult` — every evidence record it produces says
  `FROZEN_RUNTIME_REFERENCE` and "not a real provisioning outcome" in plain text. No
  live call is made to INFRA-AGAIN's API.
- Why not live: INFRA-AGAIN's frozen baseline is a real running service on this
  machine; even a "fake cloud" provisioning call against it is a real, stateful
  mutation of a frozen system this task forbids touching.

## QA Again — `HARNESS`

- QA Again has no running local instance (E7 finding: `STUB_ONLY`).
- `qa_adapter.py` builds a canonical `QARequest` and runs a `ContractQAStub`: the
  quality gate (`APPROVED`/`REJECTED`) is derived deterministically from the real
  upstream `EngineeringResult`'s own verify/test pipeline stages — never a free-text
  guess, never fabricated independent of real data. Every evidence record says
  `HARNESS` explicitly.

## PM Again — `UNAVAILABLE`

- PM Again has no running local instance and no canonical `PMStatus` usage anywhere in
  the pre-E8 codebase (E7 finding: `STUB_ONLY`, stub HTTP calls only).
- `pm_adapter.build_pm_status_placeholder()` returns `None` — Conductor does not
  fabricate a `PMStatus` to fill the gap, and does not build PM features to
  compensate. The golden flow marks PM `NOT_USED`, which the task's own PMStatus
  binding requirement explicitly allows (binding must exist; runtime use is optional).

## What this means for `DIRECT_PROVIDER_RUNTIME_BYPASS`

The **new** E8 orchestration runtime (`app/orchestration/`,
`app/routers/orchestration.py`, `app/integration/account_again_client.py`,
`app/integration/lacc_client.py`) has zero direct AI-provider-SDK call sites — grep-
verified. The **pre-existing** deliberation engine, skill AUTO-router, multi-AI panel,
and golden-flow decomposition (`app/adapters/*.py`, called from
`app/routers/{deliberation,skills,multi_ai,golden_flow}.py`) still call AI providers
directly, because migrating them requires a LACC execution endpoint that does not exist
today (see Idea → Code section above). This is reported honestly in the final E8
report as `DIRECT_PROVIDER_RUNTIME_BYPASS=FOUND_IN_LEGACY_NON_ORCHESTRATION_PATHS`
rather than claimed clean.
