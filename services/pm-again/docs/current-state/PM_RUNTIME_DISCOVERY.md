# PM AGAIN RUNTIME DISCOVERY REPORT

> Generated: 2026-08-12 | Discovery-only, no implementation performed

---

REPO_PATH=/Users/kanphong/PM-AGAIN
REPO_NAME=PM-AGAIN
REMOTE=https://github.com/gunaex/PM-Again
BRANCH=main
HEAD=62c91991904463c3c442e6fbb589119e628b0c4c
LATEST_TAG=NONE

WORKTREE_STATUS=Clean — no uncommitted changes, no staged changes, no stashes.

PM_RUNTIME_CLASS=FUNCTIONAL_STANDALONE

PM_UI_STATUS=REAL
PM_BACKEND_STATUS=REAL
PM_DOMAIN_STATUS=REAL
PM_CONTRACT_STATUS=DIVERGENT
PM_INTEGRATION_STATUS=NONE

---

## TECH_STACK

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend framework | FastAPI | 0.115.0 |
| Backend server | Uvicorn | 0.30.6 |
| ORM | SQLAlchemy | 2.0.35 |
| Validation | Pydantic | 2.9.2 |
| Frontend framework | React (Vite) | 19.2.7 |
| Build tool | Vite | 8.1.1 |
| Styling | Tailwind CSS | 4.3.3 |
| Gantt chart | frappe-gantt | 1.2.2 |
| HTTP client | Axios | 1.18.1 |
| Markdown editor | @uiw/react-md-editor | 4.1.1 |
| Router | react-router-dom | 7.18.1 |
| PWA | vite-plugin-pwa | 1.3.0 |
| Auth (BE) | bcrypt + PyJWT (HS256) | 4.2.0 / 2.9.0 |
| Rate limiting | slowapi | 0.1.9 |
| Excel I/O | openpyxl + pandas | 3.1.5 / 2.2.3 |
| Database | SQLite (one file per project + master.db) | — |
| Language | Python 3.11 / JavaScript (ES modules) | — |
| Runtime target | Python 3.11-slim (Docker) | — |
| No queue/event broker, no message system, no Redis, no external DB | — | — |

---

## RUNTIME_ENTRY_POINTS

- **Backend API**: `uvicorn app.main:app --port 8000`
  - Health: `/api/health` → `{"status":"ok"}`
  - Swagger docs: `/docs`
- **Frontend dev**: `npm run dev` → localhost:5173 (proxies `/api` to backend)
- **Docker**: `Dockerfile` at `backend/` — Python 3.11-slim, port 8000
- **Windows quick-launch**: `start.bat` (starts both backend and frontend)
- **Deployment**: `deploy-pm-again.ps1` — Cloudflare Pages (frontend) + Fly.io (backend)
- **No worker, no scheduler, no background jobs, no CLI** beyond uvicorn

---

## MAJOR_UI_ROUTES

| Route | Screen | Classification |
|-------|--------|----------------|
| `/login` | Login page | REAL |
| `/` | Project list | REAL |
| `/:slug/functions` | Function / Requirement List | REAL |
| `/:slug/gantt` | Gantt Chart (frappe-gantt) | REAL |
| `/:slug/tasks` | Task List + Follow-up Tasks | REAL |
| `/:slug/documents` | Document List | REAL |
| `/:slug/documents/:id` | Document Detail + Signoff | REAL |
| `/:slug/notes` | Note List (quick-capture) | REAL |
| `/:slug/notes-hub` | Notes Hub (Obsidian-style wiki, lazy-loaded) | REAL |
| `/:slug/reports` | Reports Page (daily/weekly/monthly/phase-closure) | REAL |
| `/:slug/board` | Issue/Incident/Backlog Board | REAL |
| `/:slug/whiteboards` | Whiteboard List (drawio) | REAL |
| `/:slug/whiteboards/:id` | Whiteboard Editor | REAL |
| `/:slug/dashboard` | Project Dashboard (RAG, phase completion, milestones) | REAL |
| `/:slug/progress-matrix` | Progress Matrix (予定実績表 / Yotei-Jisseki) | REAL |
| `/:slug/change-requests` | Change Request Management | REAL |
| `/:slug/allocations` | Project Resource Allocations | REAL |
| `/:slug/settings` | Project Settings (project code) | REAL |
| `/resources` | Resource Pool (company-wide) | REAL |
| `/holidays` | Holidays Admin (Thai holiday calendar) | REAL |

All routes use `RequireAuth` wrapper. All data is API-backed through `axios` calling the FastAPI backend.

---

## DOMAIN_MODELS

### Master Database (master.db) — Global

| Entity | Table | Key Fields |
|--------|-------|------------|
| Project | `projects` | id, name, slug, project_type, project_category, project_code, archived |
| User | `users` | id, email, password_hash, role (pmo_admin/dev/qa/client_viewer), active, must_change_password |
| RefreshToken | `refresh_tokens` | user_id, token_hash (SHA-256), expires_at, revoked |
| ThaiHoliday | `thai_holidays` | holiday_date, name_th, name_en, year, is_special |
| Resource | `resources` | name, role, email, weekly_capacity_hours, active |
| ResourceAllocation | `resource_allocations` | resource_id, project_slug, linked_task_id, allocation_percent, start_date, end_date |
| DocumentTemplate | `document_templates` | doc_code, doc_name, phase_code, phase_name, mandatory_*, defined_by, documented_by, approved_by |

### Per-Project Database (projects/{slug}.db)

| Entity | Table | Key Fields |
|--------|-------|------------|
| Function | `functions` | function_code, name, description, type, phase, owner, status, module, priority, scope_class, complexity, pd_* (BA/UX/FE/BE/INT/QA/DevOps), performance_class, target_option_*, price_thb |
| Task | `tasks` | task_code, title, description, phase, owner, due_date, status (Todo/InProgress/Done/Blocked), priority (Low/Med/High), is_followup, linked_function_id |
| GanttItem | `gantt_items` | name, phase, start_date, end_date, progress, dependencies, linked_task_id, linked_entity_type, linked_entity_id, is_milestone, baseline_start, baseline_end |
| GanttAnnotation | `gantt_annotations` | gantt_date, content, linked_gantt_item_id, color, created_by |
| Document | `documents` | doc_code, title, phase, doc_type, status (Draft/InReview/Confirmed/Rejected), version, owner, file_path |
| DocumentSignoff | `document_signoffs` | document_id, signed_by, signed_role, status (Approved/Rejected), comment |
| Comment | `comments` | entity_type (task/document), entity_id, content, created_by |
| ActivityLog | `activity_log` | entity_type (function/task/document), entity_id, field_changed, old_value, new_value, changed_by |
| Note | `notes` | content, status (Open/PromotedToTask/PromotedToIssue), linked_task_id, linked_issue_id |
| NotePage | `note_pages` | title, content_markdown, created_by |
| NoteTag | `note_tags` | note_page_id, tag (derived index from markdown) |
| NoteLink | `note_links` | source_note_id, target_type (note/task/function/document/board_item), target_id |
| BoardItem | `board_items` | item_type (issue/incident/backlog), item_code, title, severity, status, phase, owner, linked_note_id, linked_task_id, promoted_from_id, sla_due_date |
| CodeSequence | `code_sequences` | entity_type (task/function), current_alphabet, current_number |
| ProgressActualOverride | `progress_actual_overrides` | entity_type, entity_id, actual_start_override, actual_end_override, reason |
| EffortEstimateConfig | `effort_estimate_config` | productivity_*, working_days_per_month, phase_ratio_*, contracted_total_md, rate_thb_per_md, hil_* |
| EffortEstimate | `effort_estimates` | linked_entity_type, linked_entity_id, work_type, driver_counts_json, reusability_json, delivery_mode, calculated_* |
| ChangeRequest | `change_requests` | cr_code, title, description, status, linked_document_id |
| ChangeRequestImpact | `change_request_impacts` | change_request_id, impact_type (new/modify/delete), linked_function_id, function_name |
| ReportGenerationLog | `report_generation_log` | report_type, params_json, generated_by |
| Whiteboard | `whiteboards` | title, xml_content (drawio XML), linked_entity_type, linked_entity_id |

---

## DATABASE

- **Engine**: SQLite
- **ORM**: SQLAlchemy (declarative_base, two separate bases: MasterBase, ProjectBase)
- **Architecture**: One `master.db` for global state (projects, users, resources, holidays, document templates) + one SQLite file per project at `data/projects/{slug}.db`
- **Migrations**: None (no Alembic). Schema evolution via additive column patches (`ensure_columns` + `MASTER_COLUMN_PATCHES` / `PROJECT_COLUMN_PATCHES`)
- **Seed data**: Thai holidays 2026, document templates from Excel, bootstrap admin user
- **No shared DB between PM and any other AGAIN service** ✓

**Critical finding**: PM Again stores only project-execution domain data. It does NOT duplicate:
- BusinessIntent authority
- Final DeliveryReadiness authority
- Engineering execution internals
- Infra resource state
- QA test execution details
- AI credentials
- Central identity/password authority (it has its own app-local users, but no Account Again integration)

---

## PROJECT_MODEL=REAL

Robust `Project` entity in master.db:
- `id`, `name`, `slug` (unique, URL-safe), `project_type` (simple/estimate), `project_category` (critical/non_critical/ma/rollout), `project_code` (2-4 uppercase letters for Running Code Generator), `archived`, `created_at`
- Slug auto-generated from name with collision avoidance
- Archive/delete with password gate
- No tenant/workspace concept — single-org, multi-project
- Project is PM-owned operational state, NOT a duplicate of Conductor delivery orchestration

## TASK_MODEL=REAL

- Tasks owned within per-project DB
- Status: Todo → InProgress → Done / Blocked
- Priority: Low / Med / High
- Linked to Function via `linked_function_id`
- `is_followup` flag for follow-up tasks
- due_date, phase, owner
- Tasks are manually created or generated from promoted Notes
- **No link to EngineeringWorkPackage / InfrastructureRequest / QARequest** — tasks are self-contained PM work items
- Tasks do NOT attempt to orchestrate downstream systems

## MILESTONE_MODEL=REAL

- Milestones via `GanttItem.is_milestone = True`
- Reports: upcoming milestones on project dashboard
- No dedicated milestone entity — milestones are Gantt items with is_milestone flag

## DEPENDENCY_MODEL=PARTIAL

- GanttItem has `dependencies` column: comma-separated gantt_item IDs
- Used for rendering dependency arrows in frappe-gantt
- No formal dependency type/status beyond the Gantt link
- No cross-project dependencies

## ISSUE_MODEL=REAL

- Via `BoardItem` with `item_type = "issue"` (also "incident", "backlog")
- Severity: Low/Medium/High/Critical
- SLA due_date
- Promotion lifecycle: Backlog → Issue → Incident → Task
- Linked to Notes and Tasks

## RISK_MODEL=NONE

- No dedicated risk entity
- Closest proxy: Slippage Predictor via `slippage.py` (gap-score based on elapsed time vs progress)
- Issues/Incidents serve as partial risk tracking

## PROGRESS_MODEL=REAL

- GanttItem.progress (0-100 integer)
- Progress Matrix (Yotei-Jisseki): actual dates derived from ActivityLog status changes (not manually entered), with optional hand-entered overrides in separate `ProgressActualOverrides` table
- Phase completion via document status (Confirmed vs total)

## STATUS_REPORTING=REAL

- Excel-based report generation: daily, weekly, monthly, phase_closure
- ReportGenerationLog for audit
- Project Dashboard with RAG-style status

## NOTIFICATIONS=PARTIAL

- `notification_email` column reserved but "no email sending wired up yet"
- No notification infrastructure exists at runtime

## EVIDENCE_HISTORY=REAL

- ActivityLog captures every field change on function/task/document
- Report generation logs
- Progress derived from logged status transitions (evidence-based)
- Overrides stored separately and flagged when they disagree with derived values

---

## PMSTATUS_CANONICAL_FIT=MISSING

PM Again has no `PMStatus` concept as a first-class entity or API endpoint. The closest representations:

1. **Project Dashboard** (`/api/{slug}/dashboard`): aggregated RAG status, phase completion %, overdue counts, upcoming milestones
2. **Progress Matrix** (`/api/{slug}/progress-matrix`): per-entity plan-vs-actual with delay calculation
3. **Slippage Predictor** (`/api/{slug}/slippage`): gap-scores and overdue flags

These are SEMANTICALLY_EQUIVALENT in spirit to what PMStatus should convey, but there is no structured PMStatus envelope that Conductor could consume. A new PMStatus endpoint/contract would need to be built.

## DELIVERY_WORK_PACKAGE_FIT=NOT_PRESENT

PM Again has no concept of DeliveryWorkPackage. No search hit for "DeliveryWorkPackage", "BusinessIntent", "Conductor", or "orchestration" anywhere in the codebase. Tasks are the closest analogue but are manually managed, not derived from external work packages.

---

## CONDUCTOR_INTEGRATION=NOT_PRESENT
## ACCOUNT_AGAIN_INTEGRATION=NOT_PRESENT
## LOCAL_AI_CONTROL_CENTER_INTEGRATION=NOT_PRESENT
## IDEA_TO_CODE_INTEGRATION=NOT_PRESENT
## INFRA_AGAIN_INTEGRATION=NOT_PRESENT
## QA_AGAIN_INTEGRATION=NOT_PRESENT

No references to any AGAIN ecosystem service exist in the codebase. PM Again is fully standalone with zero ecosystem integration.

---

## AUTH

- **Type**: APP_LOCAL_AUTH
- bcrypt password hashing, JWT access tokens (HS256, 30 min), opaque refresh tokens (SHA-256 hashed, 7 days, revocable)
- httpOnly cookies with Secure/SameSite flags
- Roles: `pmo_admin`, `dev`, `qa`, `client_viewer`
- Password change flow + `must_change_password` enforcement
- Rate limiting on login (5/minute via slowapi)
- No OAuth, no SSO, no OIDC, no external identity provider
- Bootstrap admin account on first run if users table is empty

## TENANCY

- **Single-org**: No tenant/workspace/organization concept
- Multi-project within the single org
- Projects isolated by slug in separate SQLite files
- No cross-tenant data leakage risk because there's only one tenant
- `require_internal` guard restricts project creation to non-client roles

## AI_USAGE

**None at runtime.** Zero AI/LLM calls in the codebase. The `effort_calculator.py` explicitly states: "Everything below is arithmetic and table lookup. No ML, no external calls."

The "ClaudeCode_*.md" files in the repo root are AI-assisted *specification documents*, not runtime AI integrations.

## SECRET_HANDLING

- JWT_SECRET_KEY: ENV_REFERENCE only (`.env.example` has empty placeholder; actual value set via `fly secrets`)
- Admin password: auto-generated on first bootstrap if env vars unset, printed once
- No tracked real secrets found
- Password hashes: bcrypt (not plaintext)

SECRET_SCAN=PASS

---

## CORRELATION=NOT_PRESENT

No `correlationId`, `traceId`, `requestId`, `runId`, `externalId`, or `workPackageId` fields exist. Tasks/functions have internal `task_code`/`function_code` but these are PM-internal identifiers, not ecosystem correlation IDs.

## IDEMPOTENCY=NOT_PRESENT

No idempotency keys, deduplication logic, or external event handling. Seed operations are internally idempotent (check-before-insert) but no external API idempotency exists. Repeated Conductor messages would create duplicate PM work.

## EVENT_ARCHITECTURE=API_ONLY

Pure synchronous REST API. No outbox, no event queue, no pub/sub, no webhook consumption, no polling, no scheduler, no background workers. Integration would currently require direct API calls.

---

## CONTRACT_COMPATIBILITY

| Canonical Contract | Classification | Current PM Equivalent | Notes |
|-------------------|----------------|----------------------|-------|
| OSMessageEnvelope | MISSING_IN_PM | None | No message envelope concept |
| BusinessIntent | NOT_RELEVANT_TO_PM_RUNTIME | None | Conductor-owned |
| DeliveryWorkPackage | MISSING_IN_PM | Project (loose analogue) | No structured work package concept |
| PMStatus | MISSING_IN_PM | Dashboard aggregate + Progress Matrix | Need to build |
| EngineeringWorkPackage | MISSING_IN_PM | Task (loose analogue) | Manual tasks, not derived |
| EngineeringResult | NOT_RELEVANT_TO_PM_RUNTIME | None | Idea→Code owned |
| InfrastructureRequest | MISSING_IN_PM | Task reference possible | Not tracked |
| InfrastructureResult | NOT_RELEVANT_TO_PM_RUNTIME | None | Infra Again owned |
| QARequest | MISSING_IN_PM | Task reference possible | Not tracked |
| QAResult | NOT_RELEVANT_TO_PM_RUNTIME | None | QA Again owned |
| DeliveryReadinessResult | NOT_RELEVANT_TO_PM_RUNTIME | None | Conductor-owned |

---

## ARCHITECTURE_COLLISIONS

| Collision | Rating | Evidence |
|-----------|--------|----------|
| PM_VS_CONDUCTOR | NONE | No business intent decomposition, no specialist orchestration, no final delivery readiness, no cross-system command sequencing |
| PM_VS_IDEA_TO_CODE | NONE | No code execution, no git integration, no engineering execution. `code_generator.py` generates task/function identification codes (e.g., "CBT01"), not executable code |
| PM_VS_INFRA | NONE | No AWS/GCP/Terraform/cloud resource management. Tracks infra work via task assignment only |
| PM_VS_QA | NONE | No test execution, no QA acceptance authority. Tracks QA phase and progress via tasks/documents only |
| PM_VS_ACCOUNT | LOW | Has app-local user/password store. This is the one area of potential future collision. Users are PM-app-specific, not ecosystem-wide identities. No tenant concept. |
| PM_VS_LOCAL_AI | NONE | Zero AI runtime calls. No model providers, no API keys, no agent execution |

PM Again is a **clean PM specialist** — it tracks project execution progress without trying to be a business orchestrator, engineering executor, infra manager, QA authority, or AI router.

---

## DATA_OWNERSHIP_FINDINGS

| Entity/Data | Current PM Owner? | Canonical Owner | Aligned? | Future Action |
|------------|-------------------|-----------------|----------|---------------|
| Project | ✅ PM Again | PM Again | ✅ | Keep |
| Task/WorkItem | ✅ PM Again | PM Again | ✅ | Keep, add external package linking |
| Function/Requirement | ✅ PM Again | PM Again | ✅ | Keep |
| Gantt/Milestone | ✅ PM Again | PM Again | ✅ | Keep |
| Document | ✅ PM Again | PM Again | ✅ | Keep |
| Issue/Incident | ✅ PM Again | PM Again | ✅ | Keep |
| BoardItem (Backlog) | ✅ PM Again | PM Again | ✅ | Keep |
| ChangeRequest | ✅ PM Again | PM Again | ✅ | Keep |
| Risk | ⚠️ Missing | PM Again | ⚠️ | Build |
| Progress/Status | ✅ PM Again | PM Again | ✅ | Keep, formalize as PMStatus |
| ActivityLog | ✅ PM Again | PM Again | ✅ | Keep |
| Note/NotePage | ✅ PM Again | PM Again | ✅ | Keep |
| Whiteboard | ✅ PM Again | PM Again | ✅ | Keep |
| Resource/Allocation | ✅ PM Again | PM Again | ✅ | Keep |
| ThaiHoliday | ✅ PM Again | PM Again | ✅ | Keep |
| EffortEstimate | ✅ PM Again | PM Again | ✅ | Keep |
| BusinessIntent | ❌ | Conductor | ✅ | Not PM-owned |
| DeliveryWorkPackage | ❌ | Conductor | ✅ | Integrate as input |
| PMStatus | ⚠️ Partial | PM Again | ⚠️ | Build formal contract |
| EngineeringResult | ❌ | Idea→Code | ✅ | Reference only |
| InfrastructureResult | ❌ | Infra Again | ✅ | Reference only |
| QAResult | ❌ | QA Again | ✅ | Reference only |
| DeliveryReadinessResult | ❌ | Conductor | ✅ | Not PM-owned |
| User Identity | ⚠️ App-local | Account Again | ⚠️ | Migrate to Account Again |
| AI Credential | N/A | LACC | ✅ | Not PM-owned |

---

## REUSABLE_ASSETS

| Component | Classification | Rationale |
|-----------|---------------|-----------|
| Backend API (FastAPI) | REUSE_AS_IS | Clean, well-structured, 27 routers, real data flow |
| Frontend shell (React/Vite) | REUSE_AS_IS | Full SPA with PWA, auth, lazy loading |
| DB models (SQLAlchemy) | REUSE_WITH_ADAPTER | Solid domain model; needs correlation/idempotency fields |
| Task system | REUSE_AS_IS | Well-designed with follow-ups, priorities, phases |
| Gantt/Milestones | REUSE_AS_IS | frappe-gantt with drag/resize, dependencies, baselines |
| Dashboard (RAG) | REUSE_WITH_ADAPTER | Good foundation; needs PMStatus formalization |
| Progress Matrix | REUSE_AS_IS | Evidence-based actual dates, overrides with audit |
| Slippage Predictor | REUSE_AS_IS | Rule-based, business-day-aware, phase-delay historical averaging |
| Effort Calculator | REUSE_AS_IS | Function Point model from real customer spreadsheets |
| Risk/Issues (BoardItem) | REUSE_WITH_ADAPTER | Good domain; add dedicated Risk entity |
| Change Requests | REUSE_AS_IS | Full lifecycle with impact analysis, document gating |
| Document/Signoff | REUSE_AS_IS | Phase-based document tracking with approval workflow |
| Notes (quick-capture + wiki) | REUSE_AS_IS | Obsidian-style with tag/link indices |
| Reports (Excel) | REUSE_AS_IS | Daily/weekly/monthly/phase-closure generation |
| Thai Business Day Engine | REUSE_AS_IS | Holiday table + business day calculations |
| Running Code Generator | REUSE_AS_IS | Sequential task/function code generation per project |
| Whiteboard (drawio) | REUSE_AS_IS | Embedded drawio editor with XML persistence |
| Auth (JWT + bcrypt) | REFACTOR | Needs migration to Account Again |
| Resource Management | REUSE_AS_IS | Company-wide resource pool with allocation tracking |
| Excel Import/Export | REUSE_AS_IS | Strict header validation, import templates |
| Deployment config | REUSE_AS_IS | Fly.io (backend) + Cloudflare Pages (frontend) |
| Rate limiting | REUSE_AS_IS | slowapi on auth endpoints |

---

## REUSE_WITH_ADAPTER

- **DB models**: Add `correlation_id`, `idempotency_key`, `external_work_package_id` columns
- **Dashboard/Aggregation**: Formalize as PMStatus API endpoint
- **BoardItem/Risks**: Add dedicated Risk entity separate from Issue/Incident

## DEPRECATE_OR_REWORK

- **Auth system**: Migrate from app-local bcrypt/JWT to Account Again (OIDC/JWKS)
- **User store**: Users should come from Account Again, not local users table
- **No other deprecation needed** — the codebase is surprisingly clean

---

## TASK_WORK_PACKAGE_MAPPING_RECOMMENDATION

Based on actual PM Again domain, the cleanest mapping:

```
DeliveryWorkPackage → PM Again Project
  (or a new "WorkPackage" entity within a project if multiple packages per project)

EngineeringWorkPackage → Task with external reference
InfrastructureRequest → Task with external reference  
QARequest → Task with external reference
```

Rationale: PM Again's `Project` maps naturally to a delivery engagement. Individual specialist work packages become PM tasks linked to their external package IDs. This preserves PM Again's existing task management UX while adding traceability.

---

## PMSTATUS_MAPPING_RECOMMENDATION

PMStatus should be a new API endpoint that aggregates:

- `project/run identifier` (from Project model)
- `overall_execution_status` (from Dashboard RAG logic)
- `progress_percent` (from Gantt aggregation)
- `milestone_status` (from GanttItem milestones)
- `blocking_issues_count` (from BoardItem incidents)
- `overdue_tasks_count` (from Dashboard query)
- `phase_completion` (from document status)
- `risks` (from slippage analysis)
- `updated_at`
- `correlation_id` (new field for Conductor tracing)

---

## BUILD_TEST_RESULTS

| Test | Result |
|------|--------|
| Backend imports | ✅ PASS (with system Python 3.11 + pip install) |
| Backend startup | ✅ PASS (uvicorn on port 8000) |
| Health endpoint | ✅ PASS (`{"status":"ok"}`) |
| Auth login | ✅ PASS (bootstrap admin) |
| Password change | ✅ PASS |
| Project creation | ✅ PASS (with mandatory document seeding) |
| Task creation | ✅ PASS |
| Dashboard query | ✅ PASS (RAG data returned) |
| Frontend build | ✅ PASS (Vite + PWA, 15 precache entries) |
| Unit tests | ❌ NONE — zero test files exist in the repository |
| Integration tests | ❌ NONE |
| Lint (frontend) | oxlint configured, not run (no errors expected from clean build) |
| Type check (backend) | Python — no mypy/pyright config found |

---

## RUNTIME_SMOKE_RESULT

✅ Backend starts, health returns OK, full auth flow works (login → change password → create project → create task → view dashboard). Frontend builds successfully with PWA service worker generation. No runtime errors encountered.

---

## SECRET_SCAN=PASS

No tracked real secrets found. `.env.example` contains empty placeholders only. Password hashes use bcrypt. JWT secrets configured via environment variable with fallback warning for dev.

---

## UI_TRUTHFULNESS=PASS

All UI routes correspond to real API endpoints with real database-backed data. No mock data in production paths. No misleading "AI" labels. The Gantt chart, progress matrix, dashboard, reports, board, whiteboard, notes hub — all backed by real CRUD operations.

---

## GAP_MAP

| Gap | Current | Target | Gap | Severity | Complexity |
|-----|---------|--------|-----|----------|------------|
| G1_CORE_PM_DOMAIN | STRONG | STRONG | LOW | LOW | LOW |
| G2_CONTRACT_ALIGNMENT | DIVERGENT | ALIGNED | HIGH | HIGH | MEDIUM |
| G3_CONDUCTOR_INTEGRATION | NONE | INTEGRATED | HIGH | HIGH | MEDIUM |
| G4_ACCOUNT_INTEGRATION | NONE | INTEGRATED | HIGH | MEDIUM | MEDIUM |
| G5_LACC_AI_MIGRATION | NONE | N/A (no AI usage) | LOW | LOW | LOW |
| G6_TENANT_ISOLATION | NONE (single-org) | MULTI-TENANT | MEDIUM | MEDIUM | HIGH |
| G7_TRACE_IDEMPOTENCY | NONE | COMPLETE | HIGH | HIGH | MEDIUM |
| G8_PMSTATUS_GENERATION | NONE | COMPLETE | HIGH | HIGH | LOW |
| G9_SPECIALIST_WORK_LINKING | NONE | PARTIAL | MEDIUM | MEDIUM | LOW |
| G10_UI_TRUTHFULNESS | PASS | PASS | NONE | NONE | NONE |
| G11_TEST_COVERAGE | NONE | MINIMAL | HIGH | HIGH | MEDIUM |
| G12_DEPLOYMENT_HARDENING | EXISTING | HARDENED | MEDIUM | MEDIUM | MEDIUM |

---

## SHOULD_BUILD_FROM_SCRATCH=NO

PM Again has a **strong, real, well-architected standalone implementation**. Building from scratch would discard significant working value.

### KEEP

- Entire backend API (FastAPI, 27 routers)
- Entire frontend (React/Vite, 21 pages, PWA)
- All DB models and SQLite-per-project architecture
- Task system, Gantt, milestones, dashboard, progress matrix
- Effort calculator, change requests, document system
- Notes (quick-capture + wiki), whiteboards
- Thai Business Day Engine
- Reports generation
- Excel import/export
- Resource management
- Rate limiting, security headers
- Deployment config (Fly.io + Cloudflare Pages)

### ADAPT

- Auth: Migrate from app-local to Account Again OIDC
- User model: Replace local `users` table with Account Again identity
- DB models: Add correlation_id, idempotency_key, external_work_package_id columns
- Dashboard: Formalize as PMStatus endpoint
- BoardItem: Consider adding dedicated Risk entity

### BUILD_NEW

- PMStatus API contract and endpoint
- Conductor integration client (consume DeliveryWorkPackage, produce PMStatus)
- Correlation/idempotency middleware
- Account Again integration (OIDC client, JWKS validation)
- Multi-tenant isolation (if needed)
- Test suite (pytest + React Testing Library)
- Tenant field on all project-scoped queries

### DEPRECATE

- Local auth (after Account Again migration)
- Local user management (after Account Again migration)
- Nothing else needs deprecation

---

## RECOMMENDED_NEXT_IMPLEMENTATION_SEQUENCE

1. **Add correlation/idempotency infrastructure**: Add `correlation_id` and `idempotency_key` columns to master and project DBs, create middleware
2. **Build PMStatus contract and endpoint**: Formalize the dashboard aggregation as a structured `PMStatus` API
3. **Conductor integration**: Implement DeliveryWorkPackage consumption → PM project/task mapping, PMStatus production
4. **Account Again integration**: Replace local auth with OIDC, migrate users
5. **Test suite**: Establish pytest + React Testing Library foundation
6. **Tenant isolation**: Add tenant_id to master schema if multi-tenancy needed
7. **Specialist work linking**: Add external work package reference fields to Task model

---

## FILES_CREATED_OR_UPDATED

- `docs/current-state/PM_RUNTIME_DISCOVERY.md` (this file)

---

## GIT_STATUS_AFTER_DISCOVERY

- Working tree: clean (discovery document is new, not committed)
- No runtime changes made
- No contracts modified
- No push performed

---

PM_DISCOVERY_FINAL_STATUS=PM_AGAIN_RUNTIME_DISCOVERY_COMPLETE
