# QA Again ↔ Conductor Main Boundary

## Authority split

```
Conductor Main
  → QARequest producer
  → orchestration / DeliveryRun authority
  → DeliveryReadinessResult authority (final)

QA Again
  → QARequest consumer
  → test execution / evidence / defect / sign-off authority
  → QAResult authority (final, for QA verdict only)
```

QA Again never computes a `DeliveryReadinessResult`. Conductor never
recomputes a QA verdict from QA Again's raw tables (defects, cycles,
sign-offs) — it only reads the canonical `QAResult` QA Again produces.

## Wire path

```
Conductor Main                              QA Again
───────────────                              ────────
build_qa_request()
  ↓ canonical QARequest
QAAgainClient.dispatch_qa_request()
  → Bearer <CONDUCTOR_MAIN service token>
  → POST /api/ecosystem/qa-requests   ──────→ require_conductor_service_identity
                                               (verifies token against Account
                                               Again JWKS; rejects if systemId
                                               != CONDUCTOR_MAIN)
                                                 ↓
                                               canonical schema validation
                                                 ↓
                                               ecosystem_intake.register_
                                               external_qa_request()
                                               (idempotent on Idempotency-Key)
                                                 ↓
                                               mapping_service.intake_qa_request()
                                               → find/create QA project for
                                                 workPackageId
                                               → map to TestCycle if a
                                                 PUBLISHED revision exists,
                                                 else stay RECEIVED/unmapped
  ← {externalQARequestId, testCycleId,
     status, created}              ←──────
  (dispatch recorded, SENT)

  ... real QA execution happens asynchronously, on QA Again's own timeline ...

QAAgainClient.get_qa_result()
  → GET /api/ecosystem/qa-requests/
    {qaRequestId}/qa-result          ──────→ qa_result_service.build_qa_result()
                                               (aggregates real TestCycle/
                                               Defect/SignOff state)
  ← canonical QAResult                ←──────
    or 404 if not ready yet
svc.intake_result(..., "QAResult", ...)
  ↓
evaluate_readiness() (unchanged —
already treats REJECTED/PENDING/
APPROVED correctly)
```

## Why dispatch-qa became two calls

The pre-QA-E5 `HARNESS` adapter produced a `QAResult` synchronously,
inside the same `dispatch-qa` call, because it was a deterministic rule
evaluated against `EngineeringResult` — no actual test execution
happened. Real QA Again execution does not complete within an HTTP
request. `dispatch-qa` now only sends the `QARequest` and records the
dispatch; `refresh-qa-result` (new) polls QA Again for the result,
matching the same pattern PM Again's `refresh-pm-status` already used —
authenticated HTTP polling, no event broker.

## Fail-closed guarantees

- QA Again unreachable at dispatch time → `QAAgainUnavailableError` →
  dispatch marked `FAILED`, HTTP 502. Never a fabricated `SENT`.
- QA Again has no result yet (or is unreachable) at refresh time →
  `fetch_result()` returns `None`. Never a fabricated `QAResult`.
- Conductor never treats `QAResult.qualityGate == "PENDING"` as approved,
  and `APPROVED` alone does not force `READY_FOR_DELIVERY` — it's one
  input among engineering/infrastructure/QA gates in
  `orchestration/readiness.py`, unchanged by this work.

## What QA Again must not become

QA Again stores only its own integration bookkeeping about a QARequest
(`ExternalQARequest`: `qa_request_id`, `correlation_id`,
`delivery_run_id`/`business_intent_id` if given, artifact references,
mapped project/cycle). It does not persist Conductor's `BusinessIntent`,
`DeliveryRun` orchestration state, or `DeliveryReadinessResult`.
