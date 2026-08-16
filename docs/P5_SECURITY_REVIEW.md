# P5 — RC Security Review

Targeted review after the relay + read-auth changes. No new release blockers.

| Area | Finding | Status |
|---|---|---|
| Service authentication | Conductor relay verifies Account Again RS256 JWT via JWKS; only `systemId == DOCUMENT_AGAIN` accepted. DOCUMENT_AGAIN cannot dispatch into PM/QA (their own `require_conductor_service_identity` blocks it). | PASS |
| Tenant propagation | Handoff tenant comes from Document Again's validated request context (per-request X-Tenant-Id / token claim); a downstream untrusted payload cannot change the tenant — Conductor uses the validated DOCUMENT_AGAIN token + payload tenant, and PM/QA re-verify CONDUCTOR_MAIN. | PASS |
| Read auth | In `account_again` mode every non-public route requires a validated identity (reads included); only /health, /readiness, /metrics, /docs are public. | PASS |
| Handoff payload validation | Contract envelope `{name, version}` enforced; unsupported major rejected (422) in both DA and Conductor. | PASS |
| Contract version validation | `app/contracts.py` `require_compatible` + Conductor `SUPPORTED_CONTRACT` both reject unknown versions. | PASS |
| Idempotency keys | `handoff_id` unique in Conductor; `Idempotency-Key` = correlation id downstream; duplicate delivery returns the same ack, never dispatches twice. | PASS |
| Callback/ack validation | Ack `externalReferenceId` is read from the downstream response and stored; no fabricated "live" status. | PASS |
| SSRF | `CONDUCTOR_MAIN_URL` is environment-configured only; the delivery path is fixed (`/api/ecosystem/document-handoffs`); OpenAPI import never fetches remote `$ref` URLs. | PASS |
| Secrets | Service tokens/client secrets never logged; JSON logs carry only method/path/status/duration + request_id. | PASS |
| Logs | Structured JSON; no raw credentials. | PASS |
| Exports | Zip entry names are separator-free (no path traversal); OpenAPI import is 5MB-bounded. | PASS |

## Residual, non-blocking

- PNG export requires the cairo native library at runtime (documented in the runbook).
- Conductor's 7 pre-existing live-service integration test failures are unchanged
  by P5 (verified by stash) and are outside Document Again's repo boundary.
