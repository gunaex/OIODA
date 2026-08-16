# OIDA WORKSPACE — OIDA OS unified shell

OIDA OS (`Oops!…I Did It Again`) is the human-facing product. The AGAIN
Ecosystem (Account / Document / Conductor / PM / QA Again) is the internal
bounded-service architecture. This repo is **only the shell** — a stateless
React app that composes the five services over HTTP. It owns no domain truth,
no shared database, and no orchestration.

## Run (local)

```bash
npm install
npm run dev
# → http://localhost:5190
```

The shell expects the five backends running on their usual ports:

| Service | Port | Proxy prefix |
|---|---|---|
| Document Again | 8003 | `/api/da/*` |
| PM Again | 8000 | `/api/pm/*` |
| QA Again | 8002 | `/api/qa/*` |
| Conductor | 8010 | `/api/conductor/*` |
| Account Again | 8001 | `/api/account/*` |

## Authentication

Each backend issues its own `access_token` / `refresh_token` httpOnly cookies
with the **same names**. The Vite proxy (see `vite.config.js`) isolates them by
renaming `access_token` → `oida_<service>_at` (and `refresh_token` →
`oida_<service>_rt`) on the way back, then converts them into an
`Authorization: Bearer` header (or a `Cookie` header for `/auth/refresh`) on the
way in. The result: one login screen, no cookie collisions, no shared database.

Document Again runs in local mode and is called with an `X-Actor` header
(default `Owner`, configurable in the sign-out footer).

## Routes

```
/projects                                   project list
/projects/:projectId                        Project Home (composed)
/projects/:projectId/requirements           Requirement Register
/projects/:projectId/requirements/:code     human trace view
/projects/:projectId/documents/ur           UR
/projects/:projectId/documents/dr           DR
/projects/:projectId/architecture           Architecture & flows
/projects/:projectId/trace                  Traceability matrix
/projects/:projectId/planning               Planning overview
/projects/:projectId/planning/functions     Functions / workstreams
/projects/:projectId/planning/timeline      Timeline (honest, no fake dates)
/projects/:projectId/planning/tasks         Tasks
/projects/:projectId/qa                     QA validation scope
/projects/:projectId/qa/test-cases          Test cases
/projects/:projectId/qa/test-runs           Test runs
/projects/:projectId/qa/evidence            Evidence
/projects/:projectId/changes                Change requests + baselines
/projects/:projectId/history                Activity + audit
/admin                                      Account Again (users/roles/tenants)
```

## Guiding rules honored

- Technical IDs (`bsl_*`, `qah_*`, `pmh_*`, `wp_*`) never appear as primary
  titles — only in Details/Metadata where relevant.
- Excel (`xlsx`) remains the working document; the shell links to it, it does
  not re-implement DOCX/PDF.
- No fake PASS results, no fake dates, no fake owners. PM/QA gaps are shown
  honestly ("Not Scheduled", "Awaiting test design").
- Baseline V1 / V2 remain independent and inspectable.

## Architecture decision

See `OIDA_WORKSPACE_ARCHITECTURE_DECISION.md`.
