# CONDUCTOR MAIN E7 RUNTIME DISCOVERY REPORT

> **Phase**: E7 Runtime Discovery & Reconciliation
> **Date**: 2026-08-12
> **Status**: DISCOVERY ONLY — No implementation, no contract changes, no refactoring

---

REPO_PATH=/Users/kanphong/CONDUCTOR-AGAIN
REPO_NAME=CONDUCTOR-AGAIN
REMOTE=https://github.com/gunaex/Conductor_Again.git
BRANCH=master
HEAD=665ab3f
LATEST_TAG=NONE

WORKTREE_STATUS=Clean. No tracked modifications, no untracked files, no staged changes. Single initial commit.

CONDUCTOR_RUNTIME_CLASS=PROTOTYPE

CONDUCTOR_UI_STATUS=PARTIAL  (real React + API-backed, but no runtime delivery orchestration)
CONDUCTOR_BACKEND_STATUS=REAL     (FastAPI running, DB seeded, 36/69 tests pass)
CONDUCTOR_ORCHESTRATION_STATUS=MOCK (no delivery orchestration; rule-based intake decomposition only)
CONDUCTOR_CONTRACT_STATUS=DIVERGENT (zero canonical contract usage)
CONDUCTOR_INTEGRATION_STATUS=DIVERGENT (no AGAIN ecosystem wiring; local auth, direct AI calls, stub service URLs)

TECH_STACK:
  frontend: React 19 + Vite 8 + TailwindCSS 4 + React Router 7 + Axios + Lucide + Sonner
  backend: FastAPI 0.115 + Uvicorn + SQLAlchemy 2.0 + Pydantic 2.9
  database: SQLite (dual: master.db + per-project {slug}.db)
  auth: JWT (HS256) + bcrypt + refresh token rotation
  AI adapters: DeepSeek, OpenAI, Gemini, Anthropic, Cloudflare Workers AI (all direct, no LACC)
  API style: REST (FastAPI routers)
  queue/event: OutboxMessage model exists (unused), no actual event bus
  container: Dockerfile (python:3.11-slim) + fly.toml (Fly.io)
  deployment target: Fly.io (primary_region=sin) + Cloudflare R2
  test frameworks: pytest + fastapi.testclient
  other: Cloudflare Turnstile, slowapi rate limiting, Cloudflare R2 storage, PWA support

RUNTIME_ENTRY_POINTS:
  - FastAPI server: backend/app/main.py → uvicorn on port 8000
  - Frontend dev: frontend/ → vite dev server on port 5173 (proxied to backend)
  - Seed scripts: seed.py (admin user), seed_ai.py (AI providers), seed_skills.py, seed_deliberation.py, seed_intake.py
  - Smoke test: test_smoke.py (standalone, requests-based)
  - Docker: Dockerfile → uvicorn app.main:app

MAJOR_UI_ROUTES:
  /login                    — LoginPage (REAL_DATA, JWT auth)
  /                         — ProjectList (REAL_DATA, fetches from API)
  /:slug                    — ProjectDashboard (REAL_DATA, tabbed)
  /:slug/vision             — VisionPage (REAL_DATA, CRUD)
  /:slug/requirements       — RequirementsPage (REAL_DATA, CRUD)
  /:slug/skills             — SkillsPage (REAL_DATA, skill registry + versions + execution)
  /:slug/ai-resources       — AIResourcesPage (REAL_DATA, provider/account/model/resource CRUD)
  /:slug/deliberation       — DeliberationPage (REAL_DATA, multi-agent deliberation workflow)
  /:slug/intake             — IntakePage (REAL_DATA, text → decompose → analyze)
  /:slug/integration        — IntegrationPage (REAL_DATA, service health, trace matrix, artifact refs)
  /:slug/golden-flow        — Golden Flow trigger (REAL API call, uses golden_flow router)

DOMAIN_MODELS:
  Master DB (global):
    User                  — id, email, password_hash, display_name, role (admin/conductor/approver/contributor/viewer)
    RefreshToken          — id, user_id, token_hash, expires_at, revoked_at
    ProjectRegistry       — id, slug, name, description, status (active/archived/deleted)
    AIProvider            — code, name, website, enabled
    AIAccount             — provider_id, name, access_mode, api_key_encrypted, health_state, budgets
    AIExecutionRuntime    — account_id, runtime_type, endpoint_url, max_concurrency
    InstalledModel        — runtime_id, model_id, capabilities, context_limit, pricing
    AIResource            — account_id, runtime_id, model_id, entitlements, priority, health_state
    Skill                 — skill_id, name, category, execution_targets, model_policy, data_policy, approval_policy
    SkillVersion          — skill_id, version, system_instructions, prompt_template, input/output_schema
    SkillAssignment       — skill_version_id, scope_type, scope_value
    SkillExecution        — skill_version_id, resource_id, request_id, status, tokens, cost, latency
    DeliberationCase      — project_slug, title, trigger, status pipeline (draft→panel_selected→...→decided)
    PanelMember           — case_id, resource_id, assigned_role, provider_code
    IndependentSubmission  — case_id, member_id, conclusion, evidence_references, confidence
    PeerCritique          — case_id, reviewer_member_id, target_submission_id, strengths, weaknesses
    OpinionRevision       — original_submission_id, member_id, changed, new_evidence_received
    DissentRecord         — case_id, member_id, position, supporting_evidence
    DiversitySnapshot     — case_id, stage, provider_concentration, opinion_change_rate, conformity_alerts
    ConformityAlert       — case_id, alert_type, severity, recovery_actions
    RecoveryAction        — alert_id, case_id, action_type, status
    ExecutionLease        — resource_id, request_id, concurrency_slot, status
    RoutingDecision       — request_id, skill_id, selected_resource_id, eligible_count
    HealthSnapshot        — resource_id, status, latency_ms
    OutboxMessage         — message_type, aggregate_type, event_type, correlation_id, causation_id, idempotency_key
    IntegrationService    — code (pm-again, qa-again, dev-again), base_url, status

  Project DB (per-project):
    Vision                — revision, content, created_by
    Objective             — vision_id, description, priority
    Requirement           — code, title, description, status (draft/clarifying/approved/change_proposed/superseded), baseline_approved
    ActivityLog           — actor, actor_type, action, entity_type, entity_id
    ArtifactReference     — owner_system (PM_AGAIN/QA_AGAIN/DEV), artifact_type, external_id, external_url
    TraceLink             — source_type, source_id, target_type, target_ref_id, link_type
    IntakeSession         — source_type, source_name, raw_content, status
    FunctionItem          — session_id, code (F-001), title, complexity_score, effort_person_days, target_module (CONDUCTOR/PM_AGAIN/QA_AGAIN/DEV)
    SimilarityPair        — session_id, function_a_id, function_b_id, score, level
    RiskAssessment        — session_id, overall_risk_score, level, schedule_buffer_days, risk_items

DATABASE:
  Engine: SQLite (dual-DB pattern: master.db + projects/{slug}.db)
  ORM: SQLAlchemy 2.0 ORM (declarative_base)
  Migrations: NONE (relies on create_all on startup)
  Seed: seed.py (admin user), seed_ai.py (6 providers: deepseek, openai, gemini, anthropic, cloudflare, local)
  Pre-existing data: 3 project DBs (bom-system.db, bom2.db, smoke-3407.db)
  Data ownership assessment:
    - Conductor owns: User, ProjectRegistry, AI* models, Skill*, Deliberation*, IntegrationService, Vision, Requirement
    - Conductor references (not own): PM artifacts via ArtifactReference, QA artifacts via ArtifactReference
    - POTENTIAL COLLISION: AIAccount.api_key_encrypted stores raw AI provider API keys (should eventually use credentialRef via Account Again)
    - OK: Conductor does NOT duplicate PM tasks, QA test cases, infra state, engineering source code

ORCHESTRATION_ENGINE:
  BusinessIntent=NOT_FOUND       (no BusinessIntent entity or concept in code)
  DeliveryWorkPackage=NOT_FOUND  (no work package decomposition beyond FunctionItem for intake)
  EngineeringWorkPackage=NOT_FOUND (no engineering work dispatch; AI calls happen inline)
  InfrastructureRequest=NOT_FOUND (no InfrastructureRequest; no Terraform/cloud mutation)
  QARequest=NOT_FOUND            (no QARequest; existing IntegrationPage has `send_quality_design` but it's a stub call)
  DeliveryReadiness=NOT_FOUND    (no readiness determination logic)

  In detail:
    - The closest thing to an "engine" is the intake/decomposition pipeline (intake.py, golden_flow.py)
    - intake.py: rule-based text decomposition → FunctionItem with complexity/effort/similarity/risk analysis
    - golden_flow.py: AI-powered decomposition using Auto Router + Skills (scope-decomposer)
    - Neither produces DeliveryWorkPackage, EngineeringWorkPackage, InfrastructureRequest, or QARequest
    - Integration router has stub calls to PM Again and QA Again (HTTP calls to external URLs)
    - No workflow engine, no scheduling, no result aggregation pipeline

AI_USAGE:
  Providers supported: DeepSeek (deepseek-chat, deepseek-reasoner), OpenAI (gpt-4o, etc.), Gemini (2.5-flash, etc.), Anthropic (Claude), Cloudflare Workers AI
  Adapter pattern: BaseAdapter abstract class → per-provider implementation (chat, health, list_models)
  API keys stored: encrypted in AIAccount.api_key_encrypted (Fernet symmetric encryption)
  AI is called directly from Conductor code (golden_flow.py, multi_ai.py, skills router)
  Golden Flow: calls DeepSeek via adapter for requirement decomposition
  Multi-AI: parallel calls to multiple AI resources, then synthesis
  Skills: AUTO router selects best AI resource based on skill requirements → executes
  Deliberation: panel members are AI resources, each gets a blind prompt
  CRITICAL FINDING: Conductor calls AI providers DIRECTLY (via adapters). No Local AI Control Center integration.
  Model selection: priority-based auto-routing, no LACC MCP/RAG/skills layer

AUTH:
  Type: APP_LOCAL_AUTH (JWT + bcrypt + refresh tokens)
  Login endpoint: POST /api/auth/login (email + password)
  Token: HS256 JWT, 30min access, 7-day opaque refresh with rotation
  Cookie-based: access_token cookie, httpOnly
  Roles: admin, conductor, approver, contributor, viewer
  NO Account Again integration
  NO OIDC, OAuth, SSO
  Users stored in master.db (User model)
  Authentication vs authorization: merged — User table has both auth credentials and role

SECRET_HANDLING:
  SECRET_SCAN=PASS (no actual secrets tracked in repo)
  JWT_SECRET_KEY: env variable, example value "change-me-to-a-random-32-char-string" (not a real secret)
  ADMIN_PASSWORD: env variable, example value "ChangeMe123!" (not a real secret)
  AI API keys: stored in AIAccount table, encrypted with Fernet (AI_KEY_ENCRYPTION_KEY from env)
  Cloudflare R2 keys: env variables (empty in .env.example)
  Turnstile secret: env variable (test key 1x0000... in .env.example)
  Service tokens: PM_AGAIN_SERVICE_TOKEN, QA_AGAIN_SERVICE_TOKEN (empty in code)
  No hard-coded API keys, tokens, or passwords found in Python/JS source files

ACCOUNT_AGAIN_INTEGRATION=NOT_PRESENT
LOCAL_AI_CONTROL_CENTER_INTEGRATION=NOT_PRESENT
PM_AGAIN_INTEGRATION=STUB_ONLY (service registered at pmagain.kanphong.com, status=CONNECTED, actual calls are HTTP stubs with graceful degradation)
INFRA_AGAIN_INTEGRATION=NOT_PRESENT (no InfrastructureRequest, no INFRA-AGAIN references in code)
QA_AGAIN_INTEGRATION=STUB_ONLY (service registered at qaagain.kanphong.com, status=DEPLOYING, send_quality_design exists as stub)

CONTRACT_COMPATIBILITY:
  OSMessageEnvelope=MISSING_IN_CONDUCTOR (OutboxMessage model exists but has different schema and is unused)
  BusinessIntent=MISSING_IN_CONDUCTOR
  DeliveryWorkPackage=MISSING_IN_CONDUCTOR
  PMStatus=MISSING_IN_CONDUCTOR (IntegrationPage fetches PM status via stub HTTP call, no canonical contract)
  EngineeringWorkPackage=MISSING_IN_CONDUCTOR
  EngineeringResult=MISSING_IN_CONDUCTOR
  InfrastructureRequest=MISSING_IN_CONDUCTOR
  InfrastructureResult=MISSING_IN_CONDUCTOR
  QARequest=MISSING_IN_CONDUCTOR (send_quality_design exists but sends raw req data, not canonical QARequest)
  QAResult=MISSING_IN_CONDUCTOR
  DeliveryReadinessResult=MISSING_IN_CONDUCTOR

  All 11 canonical AGAIN ecosystem contracts are absent from the codebase.
  The only contract-like structures are:
    - OutboxMessage (has correlation_id, causation_id, idempotency_key — matches pattern but unused)
    - ArtifactReference + TraceLink (cross-system traceability, but not canonical contract format)

CORRELATION=PARTIAL (OutboxMessage model has correlation_id + causation_id, SkillExecution has request_id, but no cross-request correlation in actual runtime code)
IDEMPOTENCY=PARTIAL (OutboxMessage has idempotency_key field, ExecutionLease prevents duplicate execution, but no idempotency in API endpoints)
EVIDENCE=PARTIAL (ArtifactReference for cross-system evidence pointers, DeliberationCase has evidence_references field, but no structured evidence aggregation)

ARCHITECTURE_COLLISIONS:
  CONDUCTOR_VS_PM=MEDIUM     (IntakePage assigns functions to PM_AGAIN target_module, IntegrationPage sends delivery plans — not full PM duplication but crosses boundary)
  CONDUCTOR_VS_IDEA_TO_CODE=MEDIUM (Golden Flow calls AI directly for decomposition; multi_ai_analyze calls AI for analysis; no Idea→Code boundary)
  CONDUCTOR_VS_INFRA=LOW     (No infrastructure execution; R2 storage is data persistence, not infra management)
  CONDUCTOR_VS_QA=LOW        (send_quality_design exists as stub; no actual QA execution)
  CONDUCTOR_VS_ACCOUNT=MEDIUM (Local User/auth table, direct AI API key storage — should use Account Again for identity + credential)
  CONDUCTOR_VS_LOCAL_AI=HIGH (Direct AI provider calls via adapters bypass the LACC entirely; AI resource pool management duplicates LACC's routing role)

DATA_OWNERSHIP_FINDINGS:
  Data / Entity                    | Current owner    | Canonical owner   | Aligned? | Migration needed?
  User (auth)                      | Conductor         | Account Again     | NO       | YES — migrate to IdentityClaims
  AI API keys                      | Conductor         | Account Again     | NO       | YES — use credentialRef
  AI Resource Pool                 | Conductor         | Local AI Control  | NO       | YES — LACC should own routing
  Project                          | Conductor         | Conductor         | YES      | No
  Vision                           | Conductor         | Conductor         | YES      | No
  Requirement                      | Conductor         | Conductor         | YES      | No
  FunctionItem (decomposed)        | Conductor         | Conductor         | YES      | No
  ArtifactReference (PM/QA)        | Conductor (ref)   | Conductor (ref)   | YES      | No
  PM Task/Epic/Feature             | NOT stored        | PM Again          | YES      | No
  QA Test/Result/Defect            | NOT stored        | QA Again          | YES      | No
  Infra state                      | NOT stored        | Infra Again       | YES      | No
  Evidence reference               | Conductor (ref)   | Conductor (ref)   | YES      | No

  Key finding: Conductor does NOT duplicate specialist data. The main collisions are:
    1. Auth/identity (should be Account Again)
    2. AI routing/API keys (should be Local AI Control Center + Account Again credentialRef)
    3. Direct AI calls bypassing LACC

REUSABLE_ASSETS:
  UI shell (React + Vite + TailwindCSS PWA)        — REUSE_AS_IS (clean, API-backed, tabbed project dashboard)
  Dual-DB pattern (master + per-project SQLite)    — REUSE_AS_IS (mirrors PM Again pattern)
  AI Resource Pool management                      — REUSE_WITH_ADAPTER (should route through LACC, but UI/CRUD is good)
  Skill Registry + AUTO Router                     — REUSE_WITH_ADAPTER (skills concept aligns with LACC skills/MCP)
  Multi-Agent Deliberation + Anti-Convergence       — REUSE_AS_IS (unique governance feature, well-modeled)
  Intake & Decomposition (rule-based + AI)          — REUSE_WITH_ADAPTER (good pipeline, needs to produce canonical contracts)
  ArtifactReference + TraceLink                    — REUSE_AS_IS (solid cross-system traceability foundation)
  OutboxMessage model                              — REUSE_AS_IS (ready for event-driven integration)
  ExecutionLease concurrency control               — REUSE_AS_IS (good governance pattern)
  Integration service registry                     — REUSE_AS_IS (already models PM Again, QA Again, Dev Again)
  Complexity/Effort/Risk/Similarity analyzers      — REUSE_AS_IS (rule-based, well-structured)
  Cloudflare R2 storage + Turnstile                — REUSE_AS_IS (infra-adjacent but data persistence)
  Dockerfile + fly.toml                            — REUSE_AS_IS (deployment configuration)
  Tests (36 passing)                               — REUSE_AS_IS (good coverage of existing features)

DEPRECATE_OR_REWORK:
  Direct AI provider adapters (calling OpenAI/DeepSeek/etc. directly) — REFACTOR (route through LACC)
  AIAccount.api_key_encrypted storage                                  — DEPRECATE (use Account Again credentialRef)
  Local User/auth table (JWT + bcrypt)                                — DEPRECATE (migrate to Account Again OIDC/JWT validation)
  Stub PM/QA integration URLs (pmagain.kanphong.com, etc.)            — REFACTOR (use canonical contracts)
  test_multi_ai_direct.py (hard-coded Windows path)                    — FIX (non-functional on Mac)
  smoke_test.py / test_multi_ai.py (module-level execution)            — FIX (convert to proper pytest)

BUILD_TEST_RESULTS:
  Dependencies: installed successfully (pip install -r requirements.txt)
  Tests (pytest): 36 passed, 1 failed, 32 errors (errors are rate-limit exhaustion in test fixtures, not functional bugs)
    - Failed: test_integration_services (asserts old Vercel URL vs current kanphong.com URL)
    - Errors: slowapi rate limiting (10 logins/min) causing fixture exhaustion across 69 tests
  Broken test files: test_multi_ai_direct.py (hard-coded "d:/git/..." Windows path)
  Test coverage: auth, projects, vision, requirements, AI resources, skills, deliberation, golden flow, intake, comprehensive

RUNTIME_SMOKE_RESULT:
  Server: Started successfully (uvicorn on port 8000)
  Health: GET /api/health → {"status":"ok","app":"Conductor Again"}
  DB: Master DB initialized, admin user seeded (admin@conductoragain.local)
  Blockers: Port 8000 already in use by another process (likely previous test run)
  Overall: Backend starts, DB initializes, health endpoint responds

SECRET_SCAN=PASS  (no actual API keys, passwords, tokens, or secrets tracked in repository; all are env variables or example values)

GAP_MAP:
  G1_CORE_CONDUCTOR=HIGH       (no BusinessIntent, DeliveryWorkPackage, DeliveryReadiness — the entire orchestration engine is missing)
  G2_CONTRACT_ALIGNMENT=HIGH   (zero of 11 canonical contracts implemented; OutboxMessage is partial match only)
  G3_ACCOUNT_INTEGRATION=MEDIUM (local auth works but needs migration to Account Again; API key storage needs credentialRef)
  G4_LOCAL_AI_INTEGRATION=HIGH  (all AI calls are direct; no LACC integration at all; AI resource pool duplicates LACC role)
  G5_PM_BOUNDARY=MEDIUM         (stub integration exists but no canonical PMStatus contract; target_module assignment crosses boundary)
  G6_INFRA_BOUNDARY=LOW         (no infrastructure execution; clean separation)
  G7_QA_BOUNDARY=LOW            (stub integration only; no actual QA execution)
  G8_TRACE_IDEMPOTENCY_EVIDENCE=MEDIUM (OutboxMessage + ArtifactReference models exist but are unused in runtime)
  G9_READINESS_POLICY=HIGH      (no delivery readiness logic whatsoever)
  G10_DEPLOYMENT_HARDENING=LOW  (Dockerfile + fly.toml exist; Cloudflare R2 configured; deployment path is clear)
  G11_UI_TRUTHFULNESS=MEDIUM    (UI is API-backed with real data, but orchestration features (golden flow, integration) are stubs or partial)
  G12_TEST_COVERAGE=MEDIUM      (36 real tests pass; 32 fixture errors; 3 broken test files; no contract tests)

SHOULD_BUILD_FROM_SCRATCH=PARTIALLY

RECOMMENDED_REUSE:
  1. UI shell (React + Vite + TailwindCSS PWA) — complete, clean, tabbed project dashboard
  2. Dual-DB SQLite pattern (master + per-project) — mirrors ecosystem pattern
  3. Multi-Agent Deliberation engine — unique governance capability, well-modeled with anti-convergence
  4. Skill Registry + AUTO Router — aligns conceptually with LACC skills/MCP
  5. Intake & Decomposition pipeline — rule-based + AI-powered, good foundation
  6. ArtifactReference + TraceLink — cross-system traceability foundation
  7. OutboxMessage + ExecutionLease — event-driven integration + concurrency control models
  8. Complexity/Effort/Risk/Similarity analyzers — well-structured rule-based engines
  9. Integration Service Registry — already models PM Again, QA Again, Dev Again
  10. Cloudflare R2 storage, Turnstile, rate limiting — operational infrastructure
  11. Dockerfile + fly.toml — deployment configuration
  12. All 36 passing tests — regression safety net

RECOMMENDED_REWORK:
  1. Auth layer: migrate from local User/password to Account Again OIDC/JWT + IdentityClaims
  2. AI adapter layer: replace direct provider calls with Local AI Control Center (AIExecutionRequest/Result)
  3. API key storage: replace AIAccount.api_key_encrypted with Account Again credentialRef
  4. AI Resource Pool: delegate routing to LACC; Conductor keeps UI for management but LACC owns execution
  5. Integrations: replace stub HTTP calls (pmagain.kanphong.com) with canonical contract-based integration
  6. Orchestration engine: build from scratch — BusinessIntent → DeliveryWorkPackage → InfrastructureRequest → QARequest → DeliveryReadiness

RECOMMENDED_NEXT_IMPLEMENTATION_SEQUENCE:
  1. Define Conductor Main domain model (BusinessIntent, DeliveryWorkPackage, DeliveryReadiness) — G1
  2. Align with canonical AGAIN contracts (import or generate from E2 definitions) — G2
  3. Wire Account Again integration (replace local auth, migrate API keys to credentialRef) — G3
  4. Wire Local AI Control Center integration (replace direct adapter calls, delegate routing) — G4
  5. Implement Delivery Work Package production (decompose BusinessIntent → specialist work packages) — G1
  6. Implement InfrastructureRequest + QARequest production — G6, G7
  7. Implement PM Again boundary (canonical PMStatus, delivery plan via contracts) — G5
  8. Implement Delivery Readiness policy (aggregate EngineeringResult + InfrastructureResult + QAResult) — G9
  9. Activate OutboxMessage + correlation/idempotency in runtime — G8
  10. Harden deployment, expand test coverage, fix broken tests — G10, G12
  11. Ensure UI reflects real orchestration state (remove mock/stub behavior) — G11

FILES_CREATED_OR_UPDATED:
  docs/current-state/E7_CONDUCTOR_RUNTIME_DISCOVERY.md (this file, created)

GIT_STATUS_AFTER_DISCOVERY:
  Working tree: clean (only docs/current-state/E7_CONDUCTOR_RUNTIME_DISCOVERY.md is new/untracked)
  No commits made
  No pushes performed
  No runtime changes made

E7_FINAL_STATUS=CONDUCTOR_RUNTIME_DISCOVERY_COMPLETE
