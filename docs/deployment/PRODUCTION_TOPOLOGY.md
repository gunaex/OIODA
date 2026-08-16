# OIDA production topology (R16 Phase 5 / 17)

## Minimal public surface

```
oida.kanphong.com      → OIDA Web (Cloudflare Pages)
api-oida.kanphong.com  → OIDA Gateway / BFF (Fly.io)
```

No public subdomain per bounded service. Bounded services communicate over
private Fly `.internal` DNS only.

```
Browser
   |
   v
oida.kanphong.com (Cloudflare Pages)
   |
   v
api-oida.kanphong.com (Fly.io gateway)
   |
   +--> http://oida-account.internal   (Account Again — identity/SSO issuer)
   +--> http://oida-document.internal  (Document Again — document + lifecycle)
   +--> http://oida-conductor.internal (Conductor Again — orchestration)
   +--> http://oida-pm.internal        (PM Again)
   +--> http://oida-qa.internal        (QA Again)
   +--> http://oida-infra.internal     (Infra Again)
```

## Gateway routing (BFF)

```
/api/account/*   → Account Again
/api/document/*  → Document Again
/api/pm/*        → PM Again
/api/qa/*        → QA Again
/api/infra/*     → Infra Again
/api/conductor/* → Conductor Again
```

Gateway responsibilities only: session handling, ecosystem SSO propagation,
request correlation, safe error normalization, audit actor propagation.
**No business logic.**

## SSO (Phase 7)

Account Again remains the identity authority. Users authenticate once; OIDA
receives an RS256 ecosystem token (`iss`, `aud`, `exp`, tenant, role); the
gateway propagates the actor identity server-side. Passwords never flow
downstream; signing keys live in Fly secrets, never in Git.

## Data (Phase 8)

Logical databases: `account_db`, `document_db`, `pm_db`, `qa_db`, `infra_db`,
`conductor_db`. They may share one managed PostgreSQL cluster for cost but stay
logically isolated. Strict rule: PM never queries QA tables; QA never queries
Document tables; OIDA never queries backend databases directly. Cross-service
interaction is API/contract based only.

## Degraded states (Phase 22)

The gateway and OIDA must distinguish `AVAILABLE / UNAVAILABLE / UNAUTHORIZED /
NOT_BOUND / NOT_CONFIGURED / DEGRADED / EMPTY`. A service outage is never shown
as "No tasks" or "No QA scope".
