# Ecosystem Handoff Contract

## Authority chain (preserved)

```
Account Again   = Identity / Tenant / Entitlement / Trust
Document Again  = Requirement / Design / Revision / Confirmation
Conductor Main  = Orchestration / Distribution
PM Again        = Execution
QA Again        = Verification
```

Document Again never dispatches directly into PM/QA (they accept only
`CONDUCTOR_MAIN`). Design handoffs flow Document → Conductor → PM/QA.

## Relay endpoint (Conductor Main)

`POST /api/ecosystem/document-handoffs` — authenticated by a valid
`DOCUMENT_AGAIN` Account Again RS256 service token (JWKS-verified).

Versioned envelope (v1):

```json
{
  "contract": {"name": "document-again-handoff", "version": 1},
  "handoff_id": "...",
  "handoff_type": "EXECUTION | QA_VALIDATION",
  "tenant_id": "...",
  "project_id": "...",
  "baseline_id": "...",
  "requirement_ids": [...],
  "artifact_revision_ids": [...],
  "semantic_object_ids": [...],
  "change_request_id": "...",
  "target_release": "...",
  "correlation_id": "...",
  "source_service": "DOCUMENT_AGAIN",
  "payload_snapshot": {...}
}
```

## Mapping (Conductor-owned, not Document Again)

- EXECUTION → canonical PM `DeliveryWorkPackage`.
- QA_VALIDATION → canonical QA `QARequest`.

## Idempotency

- `handoff_id` is unique in Conductor; repeated delivery returns the same
  acknowledgement and never dispatches twice.
- Downstream `Idempotency-Key` = `DOCUMENT_AGAIN:{handoff_id}`.

## Acknowledgement

Conductor returns `{contract, handoff_id, handoff_type, status, correlationId,
externalReferenceId, duplicate, acknowledgedAt}`. `externalReferenceId` is the
PM/QA reference, persisted on Document Again's handoff record.

## Handoff lifecycle (Document Again)

`DRAFT → QUEUED → DELIVERED_TO_CONDUCTOR → ACKNOWLEDGED | FAILED → CANCELLED`
(plus `SENT` kept for backward compatibility). "Accepted by Conductor" is a
distinct event from "accepted by PM/QA".
