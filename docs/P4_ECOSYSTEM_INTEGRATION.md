# P4 — Live PM / QA Integration Contract Findings

## Authority chain (observed, not inferred)

```
Account Again   = Identity / Tenant / Entitlement / Trust Authority
Document Again  = Requirement / Design / Revision / Confirmation Authority
Conductor Main  = Ecosystem orchestration (holds the CONDUCTOR_MAIN service identity)
PM Again        = Execution Authority
QA Again        = Verification Authority
```

Document Again must **not** impersonate another service. Live handoffs therefore
flow through the ecosystem orchestrator:

```
Document Again ──(EXECUTION_REQUESTED / QA_VALIDATION_REQUESTED)──▶ Conductor Main ──▶ PM Again / QA Again
```

## Exact contract gap (verified against source)

### PM Again (`/Users/kanphong/PM-AGAIN`)
- Intake: `POST {PM_AGAIN_URL}/api/ecosystem/delivery-work-packages`
- Payload: canonical **`DeliveryWorkPackage`** (workPackageId, correlationId,
  businessIntentId, title, priority, state, assignments, engineeringContext, …).
- Auth: `require_conductor_service_identity` — verifies the bearer is an Account
  Again service token whose `systemId == "CONDUCTOR_MAIN"`. **DOCUMENT_AGAIN is
  rejected (403)**, by design.
- Idempotency: `Idempotency-Key` header; tenant via `X-Tenant-Id`.
- Returns: `externalWorkReferenceId`, `correlationId`, `projectSlug`, `status`, `created`.

### QA Again (`/Users/kanphong/QA-AGAIN`)
- Intake: `POST {QA_AGAIN_URL}/api/ecosystem/qa-requests`
- Payload: canonical **`QARequest`**.
- Auth: same `require_conductor_service_identity` (CONDUCTOR_MAIN only).
- Idempotency: `Idempotency-Key`; tenant via `X-Tenant-Id`.
- Result: `GET .../qa-requests/{id}/qa-result`.

### Conductor Main (`/Users/kanphong/CONDUCTOR-AGAIN`)
- Holds `CONDUCTOR_MAIN` identity; `integration/pm_again_client.py` and
  `integration/qa_again_client.py` dispatch the canonical payloads to PM/QA.

## What Document Again implements

1. **Versioned contracts** (`backend/contracts/*.json` + `app/contracts.py`) —
   every outbound payload carries `contract: {name, version}`; an unsupported
   major version is rejected, never silently misread.
2. **Durable outbox + HTTP deliverer** (`app/ecosystem_client.py`,
   `services.deliver_due_events_http`) — idempotent delivery (`Idempotency-Key`),
   tenant header, service token from Account Again, fail-closed on any error.
3. **Target = the ecosystem orchestrator.** The configured delivery URL is
   expected to be Conductor Main's relay (the only identity permitted by PM/QA).

## Live-dispatch status

- Direct PM/QA dispatch from Document Again is **intentionally PARTIAL** — it is
  blocked by the PM/QA `CONDUCTOR_MAIN`-only trust boundary, which is correct.
- A live end-to-end dispatch requires a Conductor Main relay endpoint accepting
  `DOCUMENT_AGAIN`-authenticated handoffs (recommended P5 adapter) — not present
  today, so `PM_LIVE_HANDOFF` / `QA_LIVE_HANDOFF` are PARTIAL.
- Account Again live validation IS fully live (see `scripts/live_account_again.py`,
  5/5 checks against a real running instance).
