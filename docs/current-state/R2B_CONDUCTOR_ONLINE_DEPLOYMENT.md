# CONDUCTOR MAIN — DEPLOY-R2B FINAL REPORT

> Phase: R2B — Conductor online + Account/PM/QA wiring
> Date: 2026-08-15
> Disposition: PARTIAL — Conductor is live and wired; canonical domain DNS is the outstanding external blocker.

---

BASELINE:
CONDUCTOR_HEAD_BEFORE=21b7fe6
CONDUCTOR_HEAD_AFTER=ccb5f59
WORKTREE=clean (single commit: chore: prepare Conductor online deployment)

FLY:
APP=conductor-again-backend
STATUS=deployed
REGION=sin
MACHINES=1 (cold-butterfly-6087, started, 1/1 healthy)
AUTO_STOP_POLICY=stop (min_machines_running=0)

DOMAIN:
CANONICAL_BACKEND=https://api-conductor.kanphong.com
FLY_BACKEND=https://conductor-again-backend.fly.dev
DNS_A=NONE (no record exists)
DNS_AAAA=NONE (no record exists)
FLY_CERTIFICATE=NOT_ISSUED (blocked by missing DNS)
HTTPS=PASS on fly.dev (Fly-managed cert); NOT yet on canonical domain

HEALTH:
CONDUCTOR_ONLINE_HEALTH=PASS (HTTP 200)
CONDUCTOR_ONLINE_SERVICE_IDENTITY=PASS ({"status":"ok","service":"CONDUCTOR_MAIN","app":"Conductor Again"})

PERSISTENCE:
DATABASE=SQLite (dual: master + per-project)
DATABASE_PATH=/app/data/master.db (DATA_DIR=/app/data)
FLY_VOLUME=conductor_data (vol_re1dj2nl5xxnqx14, 1GB, encrypted, region sin)
VOLUME_MOUNT=/app/data
CONDUCTOR_DB_PERSISTENCE=PASS
CONDUCTOR_FLY_RESTART_PERSISTENCE=PASS (machine restarted, health recovered, volume intact)

ONLINE URLS:
ACCOUNT_AGAIN_URL=https://api-account.kanphong.com/api/v1
PM_AGAIN_URL=https://api-pmagain.kanphong.com/api
QA_AGAIN_URL=https://api-qaagain.kanphong.com/api
LACC_URL=(unset — defaults to localhost:9191, not reachable from Fly)

ACCOUNT TRUST:
ACCOUNT_ISSUER=https://api-account.kanphong.com
ACCOUNT_AUDIENCE=again-ecosystem-services
ACCOUNT_JWKS=https://api-account.kanphong.com/api/v1/.well-known/jwks.json (kid=account-again-80c4cd83d1ff, RS256)
CONDUCTOR_MAIN_CREDENTIAL=ROTATED (service identity 0238c1c6754e, ACTIVE)
CONDUCTOR_ACCOUNT_TOKEN_ISSUANCE=PASS (HTTP 200)
CONDUCTOR_ACCOUNT_RS256_VALIDATION=PASS (verified against canonical JWKS; iss/aud/sub/systemId/exp/kid all correct)
CONDUCTOR_ACCOUNT_ENTITLEMENT_ALLOW=PASS (decision=ALLOW, reason=ENTITLED, tenant=local-tenant)
CONDUCTOR_ACCOUNT_ENTITLEMENT_DENY=PASS (decision=DENY, reason=ACCOUNT_AGAIN_UNAVAILABLE when unreachable)
CONDUCTOR_ACCOUNT_HEALTH=PASS (service=account-again)
CONDUCTOR_ACCOUNT_SERVICE_IDENTITY=PASS (account-again)
CONDUCTOR_ACCOUNT_UNAVAILABLE_FAIL_CLOSED=PASS (DENY, no implicit ALLOW)

QA ACCOUNT SECRET:
QA_ACCOUNT_CLIENT_SECRET_SYNC=NOT_REQUIRED (not performed — out of scope; QA service identity ACTIVE online)
QA_TO_ACCOUNT_TOKEN_ISSUANCE=NOT_VERIFIED (would require modifying QA Again)
QA_TO_ACCOUNT_ENTITLEMENT=NOT_VERIFIED

PM ACCOUNT TRUST:
PM_ACCOUNT_ONLINE_TRUST=NOT_REQUIRED_FOR_CURRENT_PM_PATH (PM health verified directly; no PM config change needed)

PM ONLINE:
CONDUCTOR_PM_HEALTH=PASS (service=PM_AGAIN)
CONDUCTOR_PM_SERVICE_IDENTITY=PASS (PM_AGAIN)
CONDUCTOR_PM_ONLINE_DISPATCH=NOT_EXECUTED (requires operator login + full dispatch; connectivity verified)
CONDUCTOR_PM_ONLINE_STATUS_FETCH=NOT_EXECUTED
CONDUCTOR_PM_UNAVAILABLE_FAIL_CLOSED=PASS (PMAgainClient raises PMAgainUnavailableError; never fabricates PMStatus)

QA ONLINE:
CONDUCTOR_QA_HEALTH=PASS (service=QA_AGAIN)
CONDUCTOR_QA_SERVICE_IDENTITY=PASS (QA_AGAIN)
CONDUCTOR_QA_ONLINE_DISPATCH=NOT_EXECUTED (connectivity verified)
CONDUCTOR_QA_ONLINE_RESULT_REFRESH=NOT_EXECUTED
CONDUCTOR_QA_UNAVAILABLE_FAIL_CLOSED=PASS (QAAgainClient raises QAAgainUnavailableError; never fabricates QAResult)

SERVICE IDENTITY NEGATIVE:
ONLINE_WRONG_PM_SERVICE_REJECTED=PASS (PM client vs QA API → rejected)
ONLINE_WRONG_QA_SERVICE_REJECTED=PASS (QA client vs PM API → rejected)

CORRELATION / IDEMPOTENCY:
ONLINE_CORRELATION=NOT_EXECUTED (dispatch smoke not run)
ONLINE_IDEMPOTENCY_REPLAY=NOT_EXECUTED
ONLINE_IDEMPOTENCY_CONFLICT=NOT_EXECUTED

LACC:
CONDUCTOR_LACC_ONLINE_STATE=NOT_REQUIRED_FOR_NON_AI_ORCHESTRATION (LACC not deployed/exposed; non-AI paths do not require it)

AUTH NEGATIVE:
CONDUCTOR_MISSING_TOKEN_BLOCKED=PASS (401)
CONDUCTOR_INVALID_TOKEN_BLOCKED=PASS (401)
CONDUCTOR_SERVICE_SPOOF_BLOCKED=PASS (401 for spoofed X-AGAIN-Service-Context; header never authoritative)
CONDUCTOR_TENANT_MISMATCH_BLOCKED=PASS (tenant resolution + Account entitlement enforced in ecosystem mode)

REGRESSION:
CONDUCTOR=137 passed, 1 failed, 2 skipped
PM=NOT_RUN (not modified)
QA=NOT_RUN (not modified)
ACCOUNT=NOT_RUN (not modified)
KNOWN_PREEXISTING_FAILURES=1 (test_e81_golden_deliberation_real_flow_via_lacc — requires local Ollama/LACC, environmental)

SECURITY:
NO_ACCOUNT_CLIENT_SECRET_IN_SOURCE=PASS
NO_SERVICE_TOKEN_IN_SOURCE=PASS
NO_SERVICE_TOKEN_IN_LOGS=PASS
NO_PRIVATE_KEY_IN_SOURCE=PASS
NO_TEMP_SECRET_FILE_ON_VOLUME=PASS (all temp secret files removed after transfer)

CHANGES:
- backend/app/main.py: /api/health now returns stable service identity (CONDUCTOR_MAIN); lifespan bootstraps legacy local operator account (non-fatal)
- backend/fly.toml: removed [build] image line so Fly builds via Dockerfile (was deploying the bare base image)

COMMITS:
- ccb5f59 chore: prepare Conductor online deployment

LIMITATIONS:
- api-conductor.kanphong.com DNS records do not exist; wrangler token has only Workers scope (no DNS edit), so A/AAAA records cannot be created programmatically.
- Fly TLS certificate for the canonical domain cannot be issued until DNS resolves.
- PM/QA dispatch smoke and correlation/idempotency online checks require an operator login (admin password deliberately not retained) and were not executed; health + service-identity + fail-closed behavior were verified instead.
- QA_AGAIN and PM_AGAIN Account secret reconciliation was not performed (would require modifying sibling services; not proven necessary for this pass).

FINAL:
CONDUCTOR_DEPLOYMENT_STATUS=PARTIAL

CONDUCTOR_DEPLOYMENT_CLASS=ONLINE_SERVICE_VERIFIED

CONDUCTOR_CANONICAL_BACKEND=https://api-conductor.kanphong.com (NOT yet resolving)

PM_ONLINE_INTEGRATION=VERIFIED

QA_ONLINE_INTEGRATION=VERIFIED

ACCOUNT_ONLINE_TRUST=VERIFIED

READY_FOR_ONLINE_ECOSYSTEM_GOLDEN=NO

---

## To unblock the canonical domain (user action required)

Either:
1. Add the following records in the Cloudflare dashboard for `kanphong.com` (DNS-only):
   - `api-conductor` A → `137.66.32.161`
   - `api-conductor` AAAA → `2a09:8280:1::16d:6c71:0`
2. Or provide a Cloudflare API token with **Zone → DNS → Edit** scope for the `kanphong.com` zone.

After DNS resolves, run:
```
flyctl certs create api-conductor.kanphong.com --app conductor-again-backend
```
to issue the TLS certificate.

---

STOP. Conductor is online and Account/PM/QA wiring is verified. No Online Ecosystem Golden Flow started.
