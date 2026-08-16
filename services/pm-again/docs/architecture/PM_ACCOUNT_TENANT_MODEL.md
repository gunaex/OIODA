# PM Again — Account Again Identity & Tenant Model

## Authority

Account Again owns identity, tenant, role/permission, product entitlement, AI entitlement, `CredentialRef`, `ServiceIdentity`, service authentication, audit, usage, and revocation. PM Again does not duplicate any of this — it consumes Account Again's decisions.

## Service identity

PM Again identifies itself to other services as `PM_AGAIN` (already a recognized `VALID_SYSTEM_ID` in Account Again). Conductor Main authenticates to PM Again as `CONDUCTOR_MAIN` via an Account-Again-issued RS256 service JWT (`LOCAL_OIDC_COMPATIBLE_SERVICE_AUTH`, 300s TTL) — verified against Account Again's JWKS endpoint (`GET /.well-known/jwks.json`) on every request, never trusted as a bare header (`app/ecosystem/service_auth.py::require_conductor_service_identity`). Missing token → 401. Invalid signature, wrong issuer/audience, or wrong system id → 403.

## Tenant model

- `models.Project.tenant_id` and `models.User.tenant_id` — both additive, nullable columns (`database.py::MASTER_COLUMN_PATCHES`). A project/user created before ecosystem mode existed has `tenant_id = NULL` and is exempt from tenant enforcement — no backfill migration was performed, per the "don't migrate database technology / don't rewrite existing data" discipline.
- A project's `tenant_id` is set once, at ecosystem-intake time, from the dispatching Conductor's service-token `tenantId` claim (`ecosystem/mapping_service.py::_find_or_create_project`). It is never set for manually-created projects.

## Enforcement is mode-gated, not blanket

`require_project_tenant_match` (`ecosystem_auth.py`), layered onto the project/task/pm-status routers, only actually compares tenants when `ECOSYSTEM_MODE=true`. This was a deliberate fix made during PM-E8's golden-flow test: tenant *ownership* is recorded at intake time regardless of mode (so the data is always correct), but tenant *enforcement* against local human dev sessions — which carry no tenant context of their own — must stay off by default, or every local developer would be locked out of any project that ever went through ecosystem intake. In `ECOSYSTEM_MODE=true`, a mismatch returns 404 (not 403), matching Conductor's own convention of not leaking cross-tenant existence.

Service-to-service tenant safety (Conductor cannot claim/reuse another tenant's `businessIntentId`-mapped project) is enforced unconditionally, independent of `ECOSYSTEM_MODE` — see `mapping_service.TenantMismatch`, raised as HTTP 403 in `routers/ecosystem_intake.py`.

## Local auth is demoted, not removed

`app/auth.py`'s bcrypt+JWT human login is unchanged and still works — it remains the mechanism for human session identity (`DEV_LOCAL_MODE`). What changed is that, in `ECOSYSTEM_MODE=true`, a valid local session and the correct global PM role (`pmo_admin`, etc.) are **not sufficient on their own** to reach another tenant's project — `require_ecosystem_identity` in that mode also calls Account Again's entitlement engine (`POST /entitlements/evaluate`, `productId=PM_AGAIN`) and fails closed (DENY) on any transport error, matching the fail-closed philosophy used throughout the AGAIN ecosystem's service clients.

## Known limitation

Human session identity itself was not migrated to full Account Again `IdentityClaims`/OIDC — that remains local JWT. This mirrors Conductor's own disclosed E8 limitation (see `CONDUCTOR-AGAIN/backend/app/orchestration/ecosystem_auth.py`'s docstring) and was out of scope for this integration phase per the master prompt's explicit instruction not to build production SSO.
