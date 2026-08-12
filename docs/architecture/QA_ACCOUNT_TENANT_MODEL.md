# QA Again ↔ Account Again — Identity, Tenant, Entitlement

## Authority

In `ECOSYSTEM_MODE=true`, Account Again is authoritative for:

- **Service identity** — is the caller really `CONDUCTOR_MAIN`? Verified
  via RS256 JWT against Account Again's live JWKS
  (`GET /.well-known/jwks.json`), not a header QA Again is asked to trust.
- **Tenant** — which tenant does this project/QARequest/QAResult belong
  to?
- **Product entitlement** — is the caller's tenant actually entitled to
  `QA_AGAIN`?

Local JWT auth (`backend/app/auth.py`, bcrypt + PyJWT, httpOnly cookies)
is unchanged and remains QA Again's own human-session mechanism. In
ecosystem mode it stays for **who is logged in**, but is explicitly
**not authoritative** for tenant or entitlement — those are Account
Again's calls, made live on every ecosystem-mode request
(`ecosystem/ecosystem_auth.py::require_ecosystem_identity`).

`ECOSYSTEM_MODE=false` (the default) makes every tenant/entitlement check
a no-op — local dev and the existing 41+ backend tests behave exactly as
before QA-E6.

## Two token directions

QA Again both **verifies** an inbound token (Conductor calling in) and
**obtains** its own outbound token (QA Again calling out, e.g. to
evaluate entitlement or, in a future phase, report usage):

```
Inbound (verify):
  Conductor's Authorization: Bearer <token>
    → ecosystem/service_auth.py::require_conductor_service_identity
    → account_again_client.verify_service_token()
    → RS256 signature check against live JWKS
    → issuer == "account-again-local", audience == "again-ecosystem-services"
    → systemId claim must equal "CONDUCTOR_MAIN" (else 403, even if the
      signature is genuinely valid — SERVICE_IDENTITY_SPOOF_BLOCKED)

Outbound (obtain):
  account_again_client.get_service_token()
    → POST /auth/service-token {systemId: "QA_AGAIN", clientSecret}
    → cached until ~15s before its 300s expiry
    → clientSecret read from ACCOUNT_AGAIN_CLIENT_SECRET (backend/.env,
      gitignored, never committed)
```

## Tenant enforcement

`Project.tenant_id` (nullable) is the tenant boundary. A project created
before ecosystem mode existed, or a purely local one, has `tenant_id =
NULL` and is exempt — enforcement only activates once a project actually
carries a tenant.

`require_project_tenant_match` is applied at the router level to:

- `GET /api/projects/{slug}` (project existence/access)
- `GET /api/{slug}/cycles/{cycle_id}/qa-result` (QAResult access)
- everything under `/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence/*`
  (evidence access — the most sensitive resource under a project)

A cross-tenant request gets `404`, not `403` — matching Conductor's and
PM Again's own convention of not leaking cross-tenant existence.

Ecosystem-created projects (via `POST /api/ecosystem/qa-requests`,
QA-E4) are tenant-stamped at creation from the caller's `X-Tenant-Id` /
service-token tenant claim (`ExternalQAProjectLink.tenant_id`,
`Project.tenant_id`). A QARequest whose `workPackageId` already maps to a
project owned by a *different* tenant is rejected
(`TenantMismatch` → HTTP 403) rather than silently reassigned.

## Verified live (not mocked)

- `tests/test_live_service_auth.py` — QA Again obtains a real service
  token from the running Account Again and verifies it via real JWKS,
  round-trip. Also proves a validly-signed-but-wrong-system token
  (QA_AGAIN's own) is rejected by the Conductor-only intake boundary.
- `tests/test_ecosystem_entitlement.py` — `local-tenant` (bootstrapped
  with an ACTIVE `QA_AGAIN` `ProductEntitlement` by Account Again's own
  `scripts/bootstrap.py`) gets a live `ALLOW`; an unentitled tenant gets a
  live `DENY` — both against the real running Account Again, not a stub.
- `tests/test_ecosystem_intake_api.py` — missing/invalid Conductor
  service tokens are rejected for real (401/403) against the live JWKS
  endpoint.

## Known limitation (disclosed, not hidden)

Human identity migration to Account Again `IdentityClaims` is out of
scope for QA-E6, same disclosed limitation PM-E6 stated. What's live is
Account Again's authority over **tenant** and **product entitlement** —
not a full OIDC replacement of QA Again's local human session mechanism.
