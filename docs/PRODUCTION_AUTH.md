# Production Auth

## Modes

- `AUTH_MODE=local` — deterministic development actor (X-Tenant-Id scoping).
- `AUTH_MODE=account_again` — production; every non-public route requires a
  validated Account Again identity (reads included).

## Public endpoints (account_again mode)

`/api/health`, `/api/readiness`, `/api/metrics`, `/docs`, `/openapi.json`.

## Required headers (account_again mode)

```
Authorization: Bearer <Account Again service token for DOCUMENT_AGAIN>
X-Account-Id: <account id>   (or X-Subject-Id)
X-Tenant-Id: <tenant id>     (request tenant; validated upstream)
```

Fail closed: missing/invalid token, DENY decision, or Account Again outage all
reject the request. No `X-Actor` header trust in production mode.

## Service identity

Document Again presents `DOCUMENT_AGAIN` to Account Again (registered in AA's
`VALID_SYSTEM_IDS`). Conductor verifies this identity on the relay; PM/QA verify
`CONDUCTOR_MAIN` only — Document Again cannot bypass Conductor.

## Auth cache

Bounded TTL (default 60s), keyed by a SHA-256 fingerprint of the credential
(never the raw token), tenant-aware, ALLOW-only; DENY and outages are always
re-evaluated live; cache failure never authorizes.
