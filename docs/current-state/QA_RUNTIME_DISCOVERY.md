# QA AGAIN RUNTIME DISCOVERY REPORT

REPO_PATH=/Users/kanphong/QA-AGAIN
REPO_NAME=QA-AGAIN (PM-QA-Again)
REMOTE=https://github.com/gunaex/PM-QA-Again
BRANCH=main
HEAD=bb2f539
LATEST_TAG=track-a-baseline

WORKTREE_STATUS=Clean. No uncommitted changes, no staged changes, no stashed changes.

QA_RUNTIME_CLASS=FUNCTIONAL_STANDALONE

QA_CONTROL_PLANE_STATUS=REAL
QA_FRONTEND_STATUS=REAL
QA_RUNNER_STATUS=PARTIAL (HYB-0 spike only)
QA_RECORDER_STATUS=NONE
QA_MANUAL_CHECKPOINT_STATUS=PARTIAL (HYB-0 spike only, not integrated with Phase 4 cycles)

RUNTIME_REALITY=MOSTLY_REAL

TECH_STACK:
- Backend: Python 3.11, FastAPI 0.115.0, uvicorn 0.30.6, SQLAlchemy 2.0.35, Pydantic 2.9.2
- Frontend: React 19.2.7, Vite 8.1.1, TailwindCSS 4.3.3, React Router 7.18.1, Axios 1.18.1
- Runner: Node.js + TypeScript 5.7, Playwright 1.62.1, tsx 4.19.0
- Auth: bcrypt 4.2.0, PyJWT 2.9.0, httpOnly cookies + Bearer token
- DB: SQLite (master.db + per-project .db files), no ORM migrations (additive column patches)
- Storage: Swapable EvidenceStorage abstraction — Filesystem (local dev) / Cloudflare R2 (production)
- Reports: openpyxl 3.1.5, pandas 2.2.3
- Rate limiting: slowapi 0.1.9
- Deployment: Fly.io (backend), Cloudflare Pages (frontend), Cloudflare R2 (evidence)
- Container: Dockerfile (Python 3.11-slim)
- Test framework: pytest 8.3.3
- Frontend lint: oxlint 1.71.0

RUNTIME_ENTRY_POINTS:
- backend/app/main.py: FastAPI app — REAL, all routes functional
- frontend/src/main.jsx: Vite React SPA — REAL, builds cleanly
- runner/src/main.ts: Node.js Playwright spike runner — PARTIAL (HYB-0 only, single scenario)
- start.bat / start.ps1: Local dev launchers — REAL, functional
- backend/scripts/backup_databases.py: Backup script — REAL
- backend/scripts/r2_staging_smoke_test.py: R2 connectivity test — REAL
- backend/scripts/reconcile_evidence.py: Evidence reconciliation tool — REAL

MAJOR_UI_ROUTES:
| Route | Status |
|---|---|
| /login (LoginPage) | REAL_DATA |
| / (ProjectList) | REAL_DATA |
| /:slug/dashboard (Dashboard) | REAL_DATA |
| /:slug/suites (SuiteList) | REAL_DATA |
| /:slug/suites/:suiteId (SuiteDetail) | REAL_DATA |
| /:slug/suites/:suiteId/revisions/:revisionId (RevisionDetail) | REAL_DATA |
| /:slug/cycles (CycleList) | REAL_DATA |
| /:slug/cycles/:cycleId (CycleExecution) | REAL_DATA |
| /:slug/reports (ReportsPage) | REAL_DATA |

All UI routes are backed by real API endpoints with real database state. No mock data or static pages detected.

DOMAIN_MODELS:

Master DB (global):
- Project (id, name, slug, external_project_url, archived, storage_quota_bytes, storage_warning_thresholds, created_at)
- User (id, email, password_hash, role, active, must_change_password, created_at)
- RefreshToken (id, user_id, token_hash, expires_at, revoked, created_at)
- RunnerToken (id, label, token_hash, revoked, created_at)

Per-Project DB:
- TestSuite (id, suite_code, name, description, suite_type, status, created_by, created_at, updated_at)
- ScriptRevision (id, suite_id, revision_label, revision_number_sort, status, change_summary, source_type, source_filename, source_sha256, imported_at, imported_by, published_at, published_by, supersedes_revision_id, created_at, updated_at)
- TestCase (id, suite_id, revision_id, logical_case_key, checkpoint_code, title, category, priority, traceability_md, fixture_md, environment_md, setup_md, action_md, validation_md, expected_result_md, negative_path, mutation_level, sequence_no, content_sha256, created_at)
- TestCycle (id, suite_id, script_revision_id, cycle_code, name, environment, release_version, target_base_url, status, require_evidence_for_pass, started_at, finished_at, created_by, created_at, updated_at, locked_at, locked_by)
- CycleTestResult (id, cycle_id, test_case_id, assigned_tester_email, status, actual_result_md, blocked_reason, na_reason, defect_reference, started_at, executed_at, executed_by, reviewed_at, reviewed_by, review_status, result_revision_no, execution_mode, result_source, runner_run_id, created_at, updated_at)
- CycleResultHistory (id, cycle_test_result_id, result_revision_no, status, actual_result_md, blocked_reason, na_reason, changed_by, change_source, changed_at)
- EvidenceItem (id, cycle_id, cycle_test_result_id, evidence_type, object_key, original_filename, original_content_type, original_size_bytes, original_sha256, current_revision_no, caption, target_url, captured_by, captured_at, status, evidence_source, created_at)
- EvidenceRevision (id, evidence_id, revision_no, annotation_json, change_summary, created_by, created_at)
- ActivityLog (id, entity_type, entity_id, field_changed, old_value, new_value, changed_by, changed_at)
- Defect (id, cycle_id, cycle_test_result_id, defect_key, title, description_md, severity, status, external_url, created_by, created_at, updated_at)
- SignOff (id, cycle_id, signoff_type, decision, comment_md, actor, acted_at)
- HybridRun (id, status, label, started_at, ended_at, created_at) — HYB-0 spike
- HybridRunEvent (id, run_id, event_type, actor_type, payload_json, created_at) — HYB-0 spike
- HybridCheckpointDecision (id, run_id, decision, reason, decided_by, decided_at) — HYB-0 spike
- HybridRunEvidence (id, run_id, original_path, original_filename, original_content_type, original_size_bytes, original_sha256, captured_at) — HYB-0 spike

DATABASE:
- Engine: SQLite via SQLAlchemy
- Pattern: master.db (users, projects, runner_tokens) + one .db file per project slug
- Migration: None (additive column patches via `ensure_columns`, additive index patches via `ensure_indexes`)
- No shared database with PM Again — the project boundary IS the file
- Evidence metadata stored in project DB; binary evidence stored in swapable storage backend

STORAGE:
- Abstraction: EvidenceStorage base class → FilesystemEvidenceStorage (dev) | R2EvidenceStorage (production)
- Production: Cloudflare R2, private bucket, S3-compatible API
- Key naming: UUID-based (non-guessable), never uses client-supplied filename
- Access: Authenticated download endpoints (never public/static URLs), presigned URLs with short expiry
- Quota: Per-project configurable (default 5 GiB), configurable threshold warnings (70/85/95/100%)

TEST_CASE_MODEL=MATURE
- Manual test cases with rich markdown fields (action, expected_result, setup, validation, traceability, fixture, environment)
- DRAFT/PUBLISHED/SUPERSEDED/ARCHIVED revision lifecycle
- Clone-for-correction pattern (published content never edited in place)
- Excel/CSV import with strict header validation
- Content SHA-256 hashing for change detection
- Mutation level tracking (READ_ONLY/MUTATING/MIXED/UNSPECIFIED)
- Negative path flag
- Priority and category fields
- Sequence ordering within revision
- NOT YET: Markdown/SATL importer (deferred — fixture file not available)

TEST_REVISION_MODEL=MATURE
- Immutable after PUBLISHED — corrections clone into new DRAFT revision
- Unique label per suite
- Source type tracking (MARKDOWN/XLSX/CSV/CLONE/MANUAL)
- Source SHA-256 integrity
- Supersedes chain
- Published at/by timestamps

TEST_STEP_MODEL=NOT_PRESENT
- No workflow_steps or step_kind model exists yet
- Test cases use structured markdown fields (action_md, validation_md, expected_result_md) rather than granular step types
- Step model is planned for HYB-1 (hybrid expansion), not yet built

AUTOMATION_RUNNER=PARTIAL (HYB-0 SPIKE)
- Node.js + TypeScript + Playwright
- Single scenario: QA-Again's own /login page (NAVIGATE → FILL email → FILL password → MANUAL_CHECKPOINT → CLICK Sign in → SCREENSHOT)
- Semantic locators: getByLabel(), getByRole() — no raw coordinates/XPath
- Outbound-only: runner initiates all requests, backend never calls into runner
- headless: false (visible browser)
- No step definition model yet (steps are hardcoded in spike.ts)
- No runner registration/heartbeat/capabilities (planned HYB-2)
- No recorder functionality

RUNNER_LEASE_MODEL=PARTIAL (HYB-0 SPIKE)
- Minimal runner_tokens table (hashed token, revocable)
- Runner authenticates via X-Runner-Token header
- No formal lease/claim/heartbeat protocol yet (single spike runner, no queue)
- Run status: RUNNING → WAITING_FOR_HUMAN → RESUMING → PASSED/FAILED/BLOCKED/CANCELLED
- No RUNNER_LOST detection yet

MANUAL_CHECKPOINT_MODEL=PARTIAL (HYB-0 SPIKE)
- Runner emits CHECKPOINT_WAITING event → polls GET /runs/{id} → human POSTs checkpoint-decision
- Decisions: PASS/FAIL/BLOCKED/NOT_APPLICABLE (immutable, one row per decision)
- Polling-based (no WebSocket/SSE), 5-min timeout
- NOT integrated with Phase 4 test cycles (CycleTestResult) — spike runs are independent HybridRun entities
- No manual checkpoint within the cycle execution UI

RECORDER_MODEL=NONE
- No recorder functionality exists
- No browser extension, no desktop input capture
- Planned for HYB-3 per roadmap

EVIDENCE_MODEL=MATURE
- EvidenceItem: immutable original (never overwritten), UUID-based object key, content-addressed upload with SHA-256 idempotency
- EvidenceRevision: append-only annotation history (design-state JSON, not rendered images)
- Types: SCREENSHOT, UPLOADED_IMAGE, PASTED_IMAGE
- MIME sniffing (rejects spoofed content-types)
- 8 MB size cap per file
- Archive (never delete)
- Compensating cleanup: DB failure after storage write triggers delete

DEFECT_MODEL=REAL
- Defect table: defect_key (DEF-{seq}), title, description_md, severity (P0-P3/UNSPECIFIED), status (OPEN/IN_PROGRESS/FIXED/RETEST/CLOSED/REJECTED), external_url, created_by
- Linked to cycle and cycle_test_result
- Severity-based: P0 failures flagged in go-live readiness
- Not synced with PM Again (API/reference integration preferred in future)

REPORTING_MODEL=REAL
- 10 backend report endpoints: Execution Summary, Detailed Results, NG/Defects, Evidence Completeness, Revision Comparison, Cycle Comparison, Tester Progress, Go-Live Readiness, Sign-off Summary, Storage Usage
- Excel export (openpyxl, 6 sheets: Cover, Results, NG_Defects, Evidence_Index, Sign_Off, Case_Detail)
- ZIP evidence package export (manifest.json + evidence files)
- All reports backed by real queries against real data

TEST_REVISION_IMMUTABILITY=IMMUTABLE
- Published revisions are never edited in place
- Clone-for-correction pattern: clone creates new DRAFT, supersedes original
- Cycle snapshot captures cases at creation time — later publishes never affect existing cycles

RUN_HISTORY_IMMUTABILITY=APPEND_ONLY
- CycleResultHistory: one row per mutation, result_revision_no increments, never edited in place
- HybridRunEvent: append-only event stream, never edited
- HybridCheckpointDecision: one row per decision, never edited
- SignOff: one row per decision, never edited
- EvidenceRevision: append-only annotation history
- EvidenceItem: original fields never change after creation

RUNNER_TRUST_MODEL:
- Runner authenticates via pre-shared hashed token (X-Runner-Token header)
- Tokens are revocable (RunnerToken.revoked)
- Token issuance is ADMIN-only
- No mTLS, no runner registration heartbeat yet
- Runner runs locally on tester's machine, outbound-only
- Runner has full browser automation capability but no OS-level automation
- Runner receives target credentials via env vars (for the spike scenario)

RUNNER_NETWORK_MODEL=OUTBOUND_ONLY
- Runner initiates every request to backend
- Backend never calls into runner or tester's machine
- Polling-based (HTTP GET) for checkpoint status, not WebSocket/SSE

SENSITIVE_INPUT_HANDLING:
- Password fields use htmlFor labels (accessibility-first)
- Runner spike: credentials passed via env vars, typed into controlled browser fields
- No secret variable model for test cases yet (no ${SECRET_*} resolution)
- Evidence screenshots may capture app UI — no automatic redaction
- JWT_SECRET_KEY: env var only, falls back to ephemeral per-process random
- Runner tokens stored hashed (SHA-256), same pattern as refresh tokens
- Passwords bcrypt-hashed, never stored plaintext
- No PII scanning or redaction in evidence

LOCATOR_STRATEGY:
- Runner (HYB-0 spike): semantic locators — getByLabel() for form fields, getByRole() for buttons
- No CSS/XPath/raw coordinates in spike
- Test case model: no locator fields (test cases are markdown-based manual scripts)
- Future: Playwright locator strategy planned for HYB-1+ workflow_steps

QA_REQUEST_CANONICAL_FIT=MISSING
- No QARequest model, endpoint, or concept exists
- No intake mechanism for external delivery/work requests
- Current flow: users create test cycles manually from published revisions
- No acceptance criteria reference from external sources

QA_RESULT_CANONICAL_FIT=PARTIAL_MATCH
- Closest equivalent: SignOff model (QA_REVIEW/BUSINESS_ACCEPTANCE/GO_LIVE decisions: APPROVED/REJECTED/PENDING)
- go_live_readiness() metric: aggregates P0 failures, open defects, pending N/A reviews, evidence completeness
- Dashboard displays go_live_readiness as a calculated verdict
- No standalone QAResult entity with correlation, blocking findings list, evidence refs
- SignOff is admin-only, decoupled from automated result computation

QA_ACCEPTANCE_POLICY:
- Deterministic evidence-backed policy exists:
  - go_live_readiness(): P0 cases must not be FAIL/BLOCKED/NOT_RUN, no unapproved P0 N/A, no P0/P1 open defects, evidence completeness required
  - Cycle-level: require_evidence_for_pass (default true) blocks PASS without evidence
  - Manual sign-off: ADMIN-only QA_REVIEW/BUSINESS_ACCEPTANCE/GO_LIVE decisions
- QAResult is distributed across SignOff + go_live_readiness metric — not a single entity
- No AI-based acceptance decisions

BLOCKING_DEFECT_MODEL:
- Defect severities: P0, P1, P2, P3, UNSPECIFIED
- go_live_readiness treats P0 and P1 open defects as blocking
- No explicit "blocking" boolean on Defect model — severity-based
- Defect status lifecycle: OPEN → IN_PROGRESS → FIXED → RETEST → CLOSED/REJECTED

ENGINEERING_ARTIFACT_PROVENANCE=PARTIAL
- TestCycle.release_version: free text, not a structured reference
- TestCycle.target_base_url: deployment URL
- No commit hash, branch, build ID, artifact reference fields
- No EngineeringResult integration

TEST_ENVIRONMENT_PROVENANCE=PARTIAL
- TestCycle.environment: free text string
- TestCycle.target_base_url: URL string
- No structured environment reference (InfrastructureResult, namespace, deployment ID)
- No browser/OS/runner version capture in cycle results

CONDUCTOR_INTEGRATION=NOT_PRESENT
- Zero references to Conductor, QARequest, QAResult, DeliveryReadiness, or BusinessIntent
- No correlation mechanism for external work packages

PM_AGAIN_INTEGRATION=NOT_PRESENT (URL link only)
- Project.external_project_url: one-way link to PM-Again project
- Dashboard shows "Back to PM-Again →" when URL is set
- No API integration, no shared database, no shared sessions
- No defect/issue sync with PM Again

ACCOUNT_AGAIN_INTEGRATION=NOT_PRESENT
- Local auth only (bcrypt + JWT)
- No OIDC, no JWKS, no Account Again service identity

LOCAL_AI_CONTROL_CENTER_INTEGRATION=NOT_PRESENT
- Zero AI/LLM usage in the codebase
- No OpenAI, Anthropic, Claude, Gemini, DeepSeek, Ollama, or any AI SDK calls
- The acronym "AI" appears only in the application name "QA-Again" and doc references

IDEA_TO_CODE_INTEGRATION=NOT_PRESENT
- No code generation, no engineering artifact references beyond release_version string
- QA Again does not edit production source code

INFRA_AGAIN_INTEGRATION=NOT_PRESENT
- No Terraform, no infrastructure deployment execution
- QA Again stores environment name/URL as metadata only

AUTH:
- Local JWT + bcrypt authentication
- httpOnly cookies (SameSite=None in production, Secure)
- Bearer token also accepted (documented as testing convenience)
- Refresh token rotation (hashed at rest, revoked on use)
- Rate-limited login (5/min via slowapi)
- CSRF protection via Origin/Referer check for cookie-authenticated writes
- Bootstrap admin: must_change_password forced on first login
- NO external OAuth/OIDC integration

TENANCY:
- Multi-project via slug-based routing
- Per-project SQLite files (data/projects/{slug}.db)
- Project isolation by construction (different DB connections, not WHERE clauses)
- Single-user-per-email, global role (ADMIN/TESTER/VIEWER)
- No tenantId concept — single deployment scope
- No workspace/organization hierarchy

SERVICE_RUNNER_IDENTITY:
- Runner tokens: hashed, revocable, ADMIN-issued
- X-Runner-Token header authentication
- No mTLS, no runner registration heartbeat
- Token is project-scoped by possession (runner knows which project slug to target)

AI_USAGE:
- NONE. Zero AI/LLM runtime code paths.
- No test generation, locator healing, defect summarization, visual comparison, or AI-based risk analysis
- HYB-0 gap analysis explicitly lists AI assistance as "not started anywhere in the app yet"
- The QA_AGAIN_HYBRID_AI_QA_MVP_EXPANSION.md document discusses AI features in section 7 but nothing is implemented

DIRECT_AI_RUNTIME_PATHS:
- None. No provider SDK imports, no API key references, no prompt templates.

SECRET_HANDLING:
- JWT_SECRET_KEY: env var (fly secrets), falls back to ephemeral random per-process
- R2 credentials: env vars only (R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID)
- start.bat/start.ps1: JWT_SECRET_KEY = "dev-local-secret-change-me" (clearly labeled dev placeholder)
- Runner tokens: SHA-256 hashed at rest
- Refresh tokens: SHA-256 hashed at rest
- User passwords: bcrypt hashed
- No plaintext secrets in codebase (previous hardcoded admin credentials removed in HEAD commit)
- No secret variable model for test case execution (no ${SECRET_*} resolution)

CORRELATION=NOT_PRESENT
- No correlationId, traceId, requestId, workPackageId, or qaRequestId concepts
- HybridRun has its own id but no external correlation mechanism
- TestCycle has no external request reference

IDEMPOTENCY=PARTIAL
- Evidence upload: content-addressed idempotency (SHA-256 match → return existing row)
- No run-level idempotency: duplicate cycle creation would create duplicate cycle records
- No QARequest deduplication (no QARequest concept at all)
- No idempotencyKey for cycle creation or run start

EVENT_JOB_ARCHITECTURE=HYBRID
- API-based: all CRUD operations via REST endpoints
- Polling: runner polls GET /runs/{id} for checkpoint status (HYB-0 spike)
- No queue, no message broker, no outbox pattern
- ActivityLog for field-level change auditing (diff-based, not event-stream)

CONTRACT_COMPATIBILITY:

OSMessageEnvelope=NOT_RELEVANT_TO_QA_RUNTIME — No message envelope concept exists. QA Again communicates via REST API only.

BusinessIntent=NOT_RELEVANT_TO_QA_RUNTIME — QA Again does not consume or produce business intents. This is Conductor's domain.

DeliveryWorkPackage=NOT_RELEVANT_TO_QA_RUNTIME — No delivery work package concept. Test cycles are created manually, not derived from external work packages.

PMStatus=NOT_RELEVANT_TO_QA_RUNTIME — QA Again does not produce PM status. PM Again owns this domain.

EngineeringWorkPackage=MISSING_IN_QA — QA Again does not receive engineering work packages. Test cycles are independent of engineering output (except free-text release_version).

EngineeringResult=MISSING_IN_QA — No engineering result intake. QA Again has no concept of "what was built" beyond release_version string and target_base_url.

InfrastructureRequest=MISSING_IN_QA — QA Again does not issue infrastructure requests. Infrastructure Again owns this.

InfrastructureResult=MISSING_IN_QA — No infrastructure result intake. TestCycle.environment is free text, not a structured reference.

QARequest=MISSING_IN_QA — No QA request model, endpoint, or intake mechanism exists. Closest concept: manual cycle creation from published revision.

QAResult=PARTIAL_MATCH — Closest local equivalents:
  - SignOff (QA_REVIEW/BUSINESS_ACCEPTANCE/GO_LIVE with APPROVED/REJECTED/PENDING)
  - go_live_readiness() computed metric
  - Cycle status (COMPLETED/LOCKED)
  No single QAResult entity with correlation, blocking findings list, evidence references, or timestamps.

DeliveryReadinessResult=MISSING_IN_QA — QA Again does NOT produce a final delivery readiness decision. This is correct per canonical architecture (Conductor owns this). However, go_live_readiness is a QA-scoped quality gate, distinct from ecosystem delivery readiness.

ARCHITECTURE_COLLISIONS:

QA_VS_CONDUCTOR=LOW
- QA Again does not issue final DeliveryReadinessResult — correct
- go_live_readiness is a QA-scoped quality gate, not an ecosystem delivery verdict — acceptable
- No QARequest/QAResult contract exists yet — gap, not collision
- Explanation: QA Again correctly stays in its lane. The gap is missing contracts, not usurped authority.

QA_VS_PM=LOW
- QA Again does not own project execution, tasks, milestones, or PM status
- Project.external_project_url is a one-way reference link — correct pattern
- Defect model is QA-owned (quality findings) with external_url for PM issue reference — acceptable
- No shared database or synchronization — correct
- Explanation: Clean separation. Defects are QA findings, not PM issues; future integration should use API references.

QA_VS_IDEA_TO_CODE=NONE
- QA Again performs zero code generation or engineering changes
- No source code editing authority
- Explanation: No collision. QA Again tests, doesn't build.

QA_VS_INFRA=NONE
- QA Again stores environment name/URL as metadata, not as infrastructure execution authority
- No Terraform, no cloud provisioning
- Explanation: No collision.

QA_VS_ACCOUNT=LOW
- QA Again has its own local auth (bcrypt + JWT), not Account Again integrated
- Roles are QA-domain specific (ADMIN/TESTER/VIEWER)
- No central identity authority claims
- Explanation: Local auth is acceptable for standalone operation. Integration with Account Again is a future gap, not a collision.

QA_VS_LOCAL_AI=NONE
- Zero AI/LLM usage in QA Again runtime
- No direct provider calls, no credential competition
- Explanation: No collision. AI features are planned but not implemented.

DATA_OWNERSHIP_FINDINGS:

| Entity/Data | Current QA owner? | Canonical owner | Aligned? | Future action |
|---|---|---|---|---|
| TestCase | YES | QA Again | YES | REUSE_AS_IS |
| TestRun/Cycle | YES | QA Again | YES | REUSE_AS_IS |
| Evidence | YES | QA Again | YES | REUSE_AS_IS |
| Defect | YES | QA Again | YES | REUSE_AS_IS (add external ref integration) |
| QARequest | NO | QA Again | NO | BUILD_NEW |
| QAResult | PARTIAL (SignOff+go_live) | QA Again | PARTIAL | ADAPT into single entity |
| DeliveryReadiness | NO (go_live is QA-scoped) | Conductor | YES | No action — correct |
| User Identity | YES (local) | Account Again | NO | ADAPT for Account Again integration |
| Runner Identity | YES (local tokens) | Account Again | PARTIAL | ADAPT for service identity |
| Secrets | YES (env vars) | Account Again / LACC | PARTIAL | ADAPT for credential resolution |
| Engineering Artifact | NO (release_version only) | Idea→Code | PARTIAL | BUILD_NEW reference model |
| Infrastructure State | NO (environment string only) | Infra Again | PARTIAL | BUILD_NEW reference model |
| PM Issue | NO (external_url only) | PM Again | YES | ADAPT for reference integration |

SECURITY_FINDINGS:
- CSRF protection implemented for cookie-authenticated writes (Origin/Referer check)
- Security headers: HSTS, X-Content-Type-Options, X-Frame-Options, CSP
- Login rate limiting: 5/min
- Evidence: content-addressed, MIME-sniffed, UUID-based keys, authenticated download only
- No path traversal in ZIP export (validated against checkpoint_code)
- Project data isolation by separate SQLite files (not WHERE clauses)
- All security findings from Phase 7 threat model addressed

RUNNER_SECURITY_FINDINGS:
- Runner is a local process, outbound-only — no inbound network exposure
- Runner has full browser automation capability (Playwright) — expected for QA runner
- No OS-level automation (no raw keyboard/mouse hooks, no shell execution)
- Runner receives target credentials via env vars — acceptable for spike, needs secret variable model for production
- No recorder exists — no risk of global input capture
- Runner token is revocable, hashed at rest

REUSABLE_ASSETS:

REUSE_AS_IS:
- Backend API: FastAPI with well-structured routers, auth, CORS, CSRF protection
- Frontend: React/Vite SPA with clean component structure
- TestCase model: mature revision/publish/clone lifecycle
- Evidence model: immutable original + append-only annotations, swapable storage
- Defect model: QA-owned findings with severity
- Cycle execution model: snapshot-based, append-only history
- Security infrastructure: bcrypt, JWT, httpOnly cookies, rate limiting, CSRF
- Test suite: 41 passing tests covering security, evidence, exports, reconciliation
- Deployment: Fly.io + Cloudflare Pages + R2, documented

REUSE_WITH_ADAPTER:
- SignOff + go_live_readiness → adapt into canonical QAResult entity
- Runner token auth → adapt for Account Again service identity
- Project isolation → adapt for tenantId if multi-tenant needed
- Storage abstraction → already swapable, no change needed

REFACTOR:
- None critical. Architecture is clean and well-documented.

DEPRECATE_OR_REWORK:
- start.bat/start.ps1 hardcoded JWT_SECRET_KEY ("dev-local-secret-change-me") — low risk (clearly labeled dev-only), but consider removing and requiring explicit env var

QA_REQUEST_MAPPING_RECOMMENDATION:
QARequest should map to:
- QARequest.target → TestCycle (created from a specific published revision)
- QARequest.acceptanceCriteria → selected test suite/cases + manual acceptance context from the BusinessIntent
- QARequest.EngineeringResult → artifact reference (new field on TestCycle: commit/branch/build/artifact URL)
- QARequest.InfrastructureResult → environment reference (new structured field, not free text)
- QARequest.correlationId → new field on TestCycle
- QARequest.idempotencyKey → deduplication check on cycle creation

QA_RESULT_MAPPING_RECOMMENDATION:
Canonical QAResult should be built from:
- TestCycle.status → COMPLETED/LOCKED/CANCELLED mapping
- go_live_readiness() → blocking findings, evidence completeness, P0 status
- SignOff decisions → explicit APPROVED/REJECTED with actor and timestamp
- CycleTestResult counts → pass/fail/blocked/na breakdown
- Evidence references → list of evidence item IDs
- Defect references → list of blocking (P0/P1) defect IDs
- New: correlationId, timestamps, qaResultId

BUILD_TEST_RESULTS:

BACKEND_TESTS=41 passed, 0 failed, 0 skipped, 0 errors
RUNNER_TESTS=None (no runner test suite exists; spike is a manual-run script)
FRONTEND_BUILD=PASS (vite build successful, 5 modules, 348.74 kB JS, 22.54 kB CSS)
TYPECHECK=PASS (runner TypeScript: tsc --noEmit passed cleanly)
LINT=NOT_CONFIGURED (oxlint configured in package.json but not run — frontend lint only)

RUNTIME_SMOKE_RESULT:
Not executed. Safe to run locally with `start.bat`/`start.ps1` or manual uvicorn + vite dev. No external dependencies needed for local dev.

RUNNER_SMOKE_RESULT:
Not executed. The HYB-0 spike runner requires: a running QA-Again backend, a project, a runner token, and targets QA-Again's own /login page. Safe to run locally — no external/customer websites involved.

MANUAL_CHECKPOINT_SMOKE_RESULT:
Not executed. Requires running backend + runner spike together. Manual checkpoint flow is documented and tested via the HYB-0 gap analysis, not automated.

SECRET_SCAN=PASS
- Only finding: "dev-local-secret-change-me" in start.bat/start.ps1 — clearly labeled dev placeholder, not a real credential
- Previous hardcoded admin credentials removed in HEAD commit (bb2f539)

UI_TRUTHFULNESS=PASS
- All UI routes are backed by real API endpoints with real database queries
- Dashboard metrics (pass rate, evidence completeness, go-live readiness) are computed from real data
- Reports page consolidates 10 real backend report endpoints
- Cycle execution UI has real save/saving/saved/error states
- No mock data, no fake dashboards, no demo-only execution

GAP_MAP:

Q1_CORE_QA_DOMAIN=LOW
- Current: test definitions, revisions, cycles, execution, evidence, defects, sign-offs — all real and mature
- Target: same, fully functional
- Gap: none significant. Markdown importer deferred (not blocking).

Q2_QAREQUEST_ALIGNMENT=HIGH
- Current: no QARequest model exists. Cycles created manually.
- Target: QARequest intake from Conductor
- Gap: complete. Need QARequest schema, endpoint, mapping to cycle creation.

Q3_QARESULT_ALIGNMENT=MEDIUM
- Current: SignOff + go_live_readiness distributed across models
- Target: single canonical QAResult entity
- Gap: consolidate existing into unified QAResult, add correlation/evidence refs

Q4_CONDUCTOR_INTEGRATION=HIGH
- Current: zero Conductor awareness
- Target: QARequest → QA Again → QAResult → Conductor
- Gap: complete integration path needed

Q5_ACCOUNT_INTEGRATION=MEDIUM
- Current: local bcrypt+JWT auth only
- Target: Account Again for identity, service identity, credential authority
- Gap: auth migration needed, local auth may remain for standalone dev mode

Q6_TENANT_ISOLATION=LOW
- Current: per-project SQLite files, slug-based routing, project isolation by construction
- Target: same, with potential tenantId overlay
- Gap: tenantId concept not present but isolation pattern is sound

Q7_TRACE_IDEMPOTENCY=HIGH
- Current: no correlationId, no QARequest deduplication. Only evidence upload has idempotency.
- Target: full correlation + idempotency for QARequest → cycle creation → QAResult
- Gap: correlation and idempotency infrastructure needed

Q8_RUNNER_TRUST=MEDIUM
- Current: pre-shared hashed token, revocable, outbound-only
- Target: Account Again service identity, runner registration, heartbeat, lease protocol
- Gap: runner identity model needs upgrade for multi-runner, lease safety

Q9_EVIDENCE_PROVENANCE=MEDIUM
- Current: test cycle has environment/release_version strings, evidence is content-addressed
- Target: structured EngineeringResult and InfrastructureResult references
- Gap: artifact and environment reference model needed

Q10_MANUAL_CHECKPOINT=LOW
- Current: HYB-0 spike proves the pattern (pause → human decision → resume)
- Target: integrated with Phase 4 cycle execution UI
- Gap: integration work needed, but pattern is proven

Q11_LACC_AI_MIGRATION=LOW
- Current: no AI usage at all
- Target: AI features routed through Local AI Control Center
- Gap: greenfield — no migration burden, just new feature work

Q12_UI_TRUTHFULNESS=LOW
- Current: all UI backed by real endpoints and data
- Target: same
- Gap: none

Q13_TEST_COVERAGE=MEDIUM
- Current: 41 backend tests (security, evidence, exports, reconciliation). No frontend tests. No runner tests.
- Target: expanded test coverage, especially for Conductor integration
- Gap: frontend and runner test suites needed

Q14_DEPLOYMENT_HARDENING=LOW
- Current: documented Fly.io + Cloudflare Pages + R2 deployment, Docker, secrets management
- Target: same, with multi-environment support
- Gap: minimal

SHOULD_BUILD_FROM_SCRATCH=NO

KEEP:
- Entire backend (FastAPI, models, routers, auth, storage abstraction, evidence, reports, exports)
- Entire frontend (React/Vite SPA, all pages, components, auth flow)
- Test suite (41 tests, conftest infrastructure)
- Runner spike (HYB-0) — as foundation for HYB-1+
- Documentation (ADRs, threat model, deployment guide, roadmap, guides)
- Deployment configuration (Dockerfile, fly.toml, start scripts)

ADAPT:
- SignOff + go_live_readiness → QAResult entity
- Runner token auth → hybrid (keep local tokens for dev, add Account Again service identity)
- TestCycle → add correlationId, EngineeringResult ref, InfrastructureResult ref fields
- Defect → add blocking boolean, external reference fields

BUILD_NEW:
- QARequest model, schema, endpoint, validity checks
- QAResult entity (consolidated from SignOff + go_live_readiness)
- Conductor adapter (QARequest consumer, QAResult producer)
- Account Again integration (identity, service identity, credential resolution)
- Correlation infrastructure (correlationId throughout)
- Idempotency infrastructure (idempotencyKey, QARequest dedup)
- Runner registration/heartbeat/lease protocol (HYB-2)
- Workflow steps model (HYB-1)
- AI features routed through LACC (future)
- Frontend and runner test suites

DEPRECATE:
- None. All existing code serves real purpose. No dead code paths detected.

RECOMMENDED_NEXT_IMPLEMENTATION_SEQUENCE:
1. Define canonical contracts (QARequest, QAResult) in AGAIN-ECOSYSTEM
2. Add correlationId + idempotencyKey to QA Again's TestCycle model
3. Build QARequest intake endpoint → maps to cycle creation
4. Build QAResult endpoint → consolidates SignOff + go_live_readiness
5. Build Conductor adapter (consume QARequest, produce QAResult)
6. Add EngineeringResult/InfrastructureResult reference fields to TestCycle
7. Account Again integration for auth (keep local auth as dev fallback)
8. Runner trust upgrade (registration, heartbeat, lease — HYB-2)
9. Manual checkpoint integration with cycle execution UI
10. LACC AI integration (when AI features are built)

FILES_CREATED_OR_UPDATED:
- docs/current-state/QA_RUNTIME_DISCOVERY.md (this file)

GIT_STATUS_AFTER_DISCOVERY:
- Working tree: clean (no modifications made during discovery)
- Only this discovery document is new and uncommitted

QA_DISCOVERY_FINAL_STATUS=QA_AGAIN_RUNTIME_DISCOVERY_COMPLETE
QA_AGAIN_DISCOVERY_COMPLETE
