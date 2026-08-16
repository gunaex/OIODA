# Conductor Main — AI Execution Boundary (E8.1)

## The rule

Every real Conductor AI execution path calls
`LocalAIControlCenterClient.execute_capability()` (`app/integration/lacc_client.py`).
Nothing else. No router, service, or adapter constructs a provider SDK client or reads
`AIAccount.api_key_encrypted` when `ECOSYSTEM_MODE=true` (the default).

```
Conductor feature (deliberation / skills / multi-AI / golden-flow)
    │
    ▼
LocalAIControlCenterClient.execute_capability(capability, prompt, ...)
    │  authenticates as CONDUCTOR_MAIN via AccountAgainClient's service token
    ▼
POST http://localhost:9191/api/ai/execute        (Local AI Control Center)
    │  verifies the inbound token against Account Again's JWKS
    │  maps AIExecutionRequest.capability -> Account Again AICapability
    ▼
Account Again entitlement gate (assertAuthorized)     — ALLOW/DENY authority
    │
    ▼
Ollama (local) execution                                — the only wired executor today
    │
    ▼
Account Again usage reporting (reportUsage)
    │
    ▼
AIExecutionResult  →  back to the Conductor feature
```

## AI orchestration vs. AI execution (the design principle this follows)

Conductor still owns, unchanged by E8.1:
- which reasoning roles participate in a deliberation, turn sequencing, independent
  first-pass isolation, critique/revision/voting/aggregation (`deliberation.py`)
- skill selection and AUTO-router scoring (`skills.py`)
- panel composition and prompt construction for its own reasoning tasks
  (`multi_ai.py`, `golden_flow.py`)

Local AI Control Center (via Account Again) owns, as of E8.1:
- provider/model selection, credential resolution, cloud/local policy enforcement,
  usage accounting, execution evidence — for every real AI call Conductor makes.

## Capability mapping

| Conductor feature | AIExecutionRequest.capability | Account Again AICapability |
|---|---|---|
| Deliberation independent submission | `GENERAL_REASONING` | `AI_AGENT` |
| Multi-AI panel analysis + synthesis | `BUSINESS_ANALYSIS` | `AI_ARCHITECTURE` |
| Golden-flow decomposition | `BUSINESS_ANALYSIS` | `AI_ARCHITECTURE` |
| Skill AUTO-router execution | `GENERAL_REASONING` | `AI_AGENT` |
| Engineering dispatch (E8, unchanged) | n/a — real `EngineeringWorkPackage` via `/api/integration/v1/work-packages` | `AI_CODE` (LACC-internal) |

The `EXECUTION_TO_ENTITLEMENT_CAPABILITY` map lives in exactly one place — LACC's
`src/app/api/ai/execute/route.ts` — Conductor never duplicates it.

## Disclosed tradeoffs

- **Provider diversity → model-family diversity.** Multi-AI panels and deliberation
  panels used to diversify across cloud provider *accounts* Conductor held credentials
  for. Since Conductor no longer selects providers or holds credentials, diversity is
  now diversity of local Ollama model family (`qwen2.5`, `llama3.1`, `gemma3`,
  `qwen2.5-coder`) — the same *intent* (independent reasoning from different model
  lineages), a different mechanism.
- **Only Ollama is wired.** LACC's `/api/ai/execute` has no cloud provider executor
  today. A request whose entitlement requires cloud (`cloudAllowed=true` doesn't force
  cloud — it permits it) still executes locally; a genuinely cloud-*required* capability
  would need a cloud executor added to LACC, which is out of E8.1's scope (LACC's own
  provider roadmap, not a Conductor concern).
- **`LEGACY_DIRECT_AI_MODE`** (`ECOSYSTEM_MODE=false`) keeps the pre-E8.1 direct-adapter
  code paths reachable for local/offline development without Account Again or LACC
  running. It is not the default and is explicitly dev-only.

## Where the boundary is enforced

`tests/test_e81_security.py` proves, live, that:
- `ECOSYSTEM_MODE=true` code paths never call `get_adapter()` (direct provider SDK) or
  `_decrypt()` (raw credential) — monkeypatched to raise if reached.
- LACC/Account Again unavailability fails closed (`FAILED`/`BLOCKED_BY_POLICY`, never a
  provider fallback).
- A nonexistent tenant is denied, and cross-tenant entitlement evaluation returns DENY.
- LACC's `/api/ai/execute` rejects missing tokens, garbage tokens, and unknown
  capabilities — all live, against the real running services.
