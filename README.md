# OIODA — AI-Ready, Human-Led Project Delivery Workspace

Monorepo for the OIDA OS ecosystem. **One git repository ≠ one backend ≠ one
database ≠ one authority.** The bounded-service separation is architectural;
the human experience is unified.

## Bounded authorities

| Service | Authority | Local | Port |
|---|---|---|---|
| Account Again | Identity + ecosystem SSO issuer | `services/account-again` | 8011 |
| Document Again | Document truth + project lifecycle | `services/document-again` | 8003 |
| Conductor Again | Workflow orchestration | `services/conductor-again` | 8010 |
| PM Again | Execution / planning truth | `services/pm-again` | 8000 |
| QA Again | Verification truth | `services/qa-again` | 8002 |
| Infra Again | Infrastructure truth | `services/infra-again` | 18090 |
| OIDA Web | Shell / UI / Council | `apps/oida-web` | 5190 |

## Develop

```bash
./scripts/dev/start.sh     # start the whole local ecosystem
./scripts/dev/status.sh    # health of every service (no credentials)
./scripts/dev/stop.sh      # stop every service
```

## Consolidate

```bash
bash scripts/consolidate.sh /path/to/oiioda   # history-preserving merge
```

## Project lifecycle (R16)

`ACTIVE → ARCHIVED → DELETE_REQUESTED → DELETED`. Archive/restore/clone are
Document Again (the lifecycle authority) endpoints; delete is tombstoned and
orchestrated per bounded service — no direct SQL across services.

## Export / import

```bash
GET  /api/projects/{id}/export          # *.oida-project package + secret scan
POST /api/projects/import               # through Document Again (idempotent)
```

## Production topology

`oida.kanphong.com` (Cloudflare Pages) → `api-oida.kanphong.com` (Fly.io
gateway/BFF) → bounded services over private Fly networking. See
`docs/deployment/PRODUCTION_TOPOLOGY.md`.

## Layout

```
apps/oida-web/        OIDA shell (React)
services/*            six bounded authorities (FastAPI)
ops/                  cloudflare / fly / github-actions / env
scripts/              dev / migration / backup / deployment
docs/                 architecture / deployment / sso / authority / acceptance
```
