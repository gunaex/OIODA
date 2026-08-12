# CONDUCTOR MAIN E8.1 — LEGACY AI EXECUTION CLOSURE

> **Phase**: E8.1 — Legacy AI Execution Closure
> **Date**: 2026-08-12
> **Builds on**: [E8_CONDUCTOR_CORE_ORCHESTRATION.md](E8_CONDUCTOR_CORE_ORCHESTRATION.md)

## What changed

E8 disclosed one gap: the new orchestration runtime routed 100% of its AI execution
through Local AI Control Center (LACC), but Conductor's pre-existing deliberation
engine, skills AUTO-router, multi-AI panel, and golden-flow decomposition still called
AI providers directly, because LACC exposed no generic `AIExecutionRequest` execution
endpoint. E8.1 closes that gap on both sides:

**Local AI Control Center** (`local-ai-control-center`, separate repo):
- Added `POST /api/ai/execute` — a real generic AIExecutionRequest → AIExecutionResult
  boundary, reusing the exact security/control chain the Idea → Code pipeline already
  used (`assertAuthorized` → Ollama execution → `reportUsage`). No second execution
  architecture.
- Added `src/lib/integration/inboundServiceAuth.ts` — LACC's first real *inbound*
  service-token verification (RS256 JWT via Account Again's JWKS). Previously LACC only
  ever verified tokens as a caller of Account Again, never as a callee of anything.
- Widened `IdentityContext.serviceSystemId` to include `CONDUCTOR_MAIN`.
- **Real bug fixed along the way**: `LOCAL_AI_CONTROL_CENTER_CLIENT_SECRET` was unset,
  so LACC could never obtain its own service token — every usage-report call
  (a hard-required-token Account Again endpoint) had been silently failing since at
  least E5.1, including in flows previously reported as verified. Rotated the secret,
  configured it in `.env.local`, and confirmed live: real usage records now land in
  Account Again with matching correlation IDs.

**Conductor Main** (this repo):
- `LocalAIControlCenterClient.execute_capability()` (`app/integration/lacc_client.py`)
  is now the real `AIExecutionGateway` — authenticates as `CONDUCTOR_MAIN` via the same
  Account Again service token used for entitlement calls, calls LACC's new endpoint,
  fails closed (never a direct provider call) on any failure.
- Migrated every real runtime AI-execution call site to the gateway, each gated behind
  `ECOSYSTEM_MODE` (default `true`) — the pre-E8.1 direct-provider path remains only as
  `LEGACY_DIRECT_AI_MODE` (`ECOSYSTEM_MODE=false`, dev-only, disclosed):
  - `multi_ai.py` — panel analysis + synthesis (`_call_one_capability_slot`,
    `_run_synthesis_via_gateway`). Provider diversity is now local-Ollama-model-family
    diversity (qwen2.5, llama3.1, gemma3, qwen2.5-coder) rather than cloud-account
    diversity — a disclosed, honest tradeoff of the credential-authority removal.
  - `golden_flow.py` — AI decomposition (`_ai_decompose_via_gateway`).
  - `ai_resources.py` — `/resources/{id}/test` (real AI execution; previously
    uninventoried in E8) and `/accounts/{id}/health-check` (credential read, gated off
    entirely in ecosystem mode rather than migrated, since it's a credential probe, not
    AI execution).
  - `skills.py` — `execute_skill` now actually executes (previously it only ever
    recorded a `"queued"` `SkillExecution` row and never ran anything — this is new
    functionality completing a half-built feature, not a migration, so it is not
    gated behind `ECOSYSTEM_MODE`).
  - `deliberation.py` — new `POST /{case_id}/members/{member_id}/generate` endpoint
    generates a panel member's independent first-pass submission via the gateway
    (deliberation previously had *no* AI execution wiring at all — panel members'
    submissions were always externally/manually POSTed to `/submit`; this is also new
    functionality, not a migration).

## Real finding: two separate capability vocabularies

Wiring `/api/ai/execute` surfaced a genuine, previously-undocumented ecosystem fact:
the canonical v2 `AIExecutionRequest.capability` enum (`CODE_PLANNING`,
`GENERAL_REASONING`, etc. — describes the *shape* of the AI task) and Account Again's
`AICapability` entitlement vocabulary (`AI_CODE`, `AI_AGENT`, etc. — describes the
*entitlement* being checked) do not share values. `EXECUTION_TO_ENTITLEMENT_CAPABILITY`
in LACC's new route is the one place that translates between them.

## Real finding: local model latency varies enough to matter

The 14B/16B local models installed (`qwen2.5:14b-64k`, `deepseek-coder-v2:16b`)
reliably exceed `generateCompletion`'s 30s timeout for a simple prompt on this machine.
Model-selection fallbacks (multi-AI panel diversity, deliberation panel diversity, the
generic endpoint's auto-select) were tuned to prefer 7B/8B/4B models after this was
found live, rather than picking blindly from the installed-models list.

## What did NOT change

- BusinessIntent/DeliveryRun/readiness/specialist-dispatch (E8's orchestration core) —
  untouched, still passing.
- The deliberation engine's turn sequencing, consensus/voting/critique/aggregation
  logic — untouched; only the provider-execution boundary for independent-submission
  generation is new.
- The skill registry's CRUD, versioning, and AUTO-router scoring/selection logic —
  untouched; only real execution was added where none existed.
- INFRA-AGAIN — not touched.
- Account Again — not modified (only called: rotate-client-secret for `LOCAL_AI_CONTROL_CENTER`
  and `CONDUCTOR_MAIN`, both pre-existing, ordinary API operations).

## Test evidence

```text
Conductor backend: 129 passed, 0 failed, 0 errors (was 117/0/0 after E8)
  +12 new tests: test_e81_security.py (11), test_e81_golden_deliberation.py (1)
Conductor frontend: build PASS
Local AI Control Center: npx tsc --noEmit clean; new route live-verified
  (real Ollama execution, real Account Again entitlement ALLOW/DENY, real usage
  records, real inbound-auth rejection of missing/garbage tokens and unknown capabilities)
```

See the E8.1 final report for the complete gate-by-gate status.
