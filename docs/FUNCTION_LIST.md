# Conductor Again — Full Function List

> **Version:** 0.1.0 MVP  
> **วันที่:** 2026-08-03  
> **Stack:** FastAPI + React/Vite + Tailwind v4 + SQLite + Cloudflare R2

---

## 📊 System Overview

| Layer | Technology | Details |
|---|---|---|
| **Backend** | FastAPI (Python 3.13) | 56 endpoints, 7 routers, dual SQLite |
| **Frontend** | React 19 + Vite 8 + Tailwind v4 | 9 pages, PWA, code splitting |
| **Database** | SQLite (master.db + per-project) | 27 models, encrypted API keys |
| **AI** | DeepSeek adapter + AUTO Router | Multi-provider, entitlement-based routing |
| **Storage** | Cloudflare R2 | Pre-signed upload/download, encrypted backups |
| **Auth** | JWT + bcrypt + refresh rotation | httpOnly cookies, role-based access |

---

## 🔐 1. Authentication & Authorization

| Function | Description |
|---|---|
| Login | Email/password → JWT access token (30 min) + opaque refresh token (7 days) |
| Logout | Clears httpOnly cookies |
| Token Refresh | Silent rotation — old refresh token consumed, new one issued |
| Get Profile | `/api/auth/me` — returns user info + role |
| Change Password | Requires current password verification |
| Role System | 5 roles: `admin`, `conductor`, `approver`, `contributor`, `viewer` |
| Rate Limiting | 100 req/min default, 10/min for login |
| Password Security | bcrypt hashing, must-change-password flag |

---

## 📁 2. Project Management

| Function | Description |
|---|---|
| Create Project | slug + name + description → auto-initializes per-project SQLite DB |
| List Projects | All non-deleted projects |
| Update Project | Rename, change description, archive |
| Project Isolation | Each project has its own `projects/{slug}.db` |

---

## 📖 3. Vision Management

| Function | Description |
|---|---|
| Add Vision | Create new immutable revision (auto-increments version) |
| View Timeline | All revisions in chronological order with latest highlighted |
| Compare Revisions | Side-by-side diff between any two revisions |
| Version Immutability | Published revisions cannot be edited |

---

## 🛡️ 4. Requirements Management

| Function | Description |
|---|---|
| Create Requirement | Code + title + description |
| List Requirements | Search by code/title/description |
| Filter | By status: draft, clarifying, approved, change_proposed, superseded |
| Sort | By code, status, or last updated date |
| Stats Dashboard | Total, approved, draft, clarifying counts |
| Baseline Tracking | `baseline_approved` flag + approver attribution |

---

## ⚡ 5. Skill Registry

| Function | Description |
|---|---|
| **Skill Catalog** | 9 pre-seeded governed skills |
| Create Skill | Define skill_id, name, category, policies |
| Version Management | Immutable versions with SHA-256 checksum |
| Publish/Revoke | Draft → Published → Revoked lifecycle |
| Skill Assignments | Assign to platform, project, role, or workflow |
| **AUTO Router** | Evaluates ALL eligible AI resources, scores 8 dimensions, selects Primary + Fallback |
| Execution History | Track every skill execution with provenance |

### Pre-seeded Skills:

| Skill ID | Name | Category |
|---|---|---|
| `vision-intake` | Vision Intake | vision |
| `domain-clarifier` | Domain Clarifier | requirement |
| `requirement-completeness` | Requirement Completeness Review | review |
| `scope-decomposer` | Scope Decomposer | planning |
| `defect-triage` | Defect Triage | analysis |
| `impact-analysis` | Impact Analysis | analysis |
| `decision-brief` | Decision Brief | decision |
| `independent-critique` | Independent Critique | review |
| `decision-judge` | Decision Judge | decision |

---

## 🌐 6. AI Resource Pool

| Function | Description |
|---|---|
| **Provider Management** | Register AI vendors (DeepSeek, OpenAI, Gemini, Anthropic, Cloudflare, Local) |
| **Account Management** | API keys encrypted at rest, last-4 display |
| **Health Check** | Real-time connectivity test against provider API |
| **Test Resource** | Send test prompt through any resource |
| **Access Modes** | OFFICIAL_API, OFFICIAL_SUBSCRIPTION_TOOL, LOCAL_MODEL, MANUAL_HANDOFF, MOCK_OR_TEST |
| **Connector Status** | SUPPORTED → PARTIALLY_SUPPORTED → MANUAL_ONLY → PLANNED → DISABLED |
| **Pool Summary** | Total/available/degraded/offline counts |
| **Sub-tabs** | Overview, Providers, Accounts, Models, Resources |

### AUTO Router Scoring (8 dimensions):

| Dimension | Weight |
|---|---|
| Capability Fit | 25% |
| Privacy/Data Policy | 20% |
| Skill Evaluation Quality | 15% |
| Current Availability | 10% |
| Historical Success | 15% |
| Estimated Cost | 7% |
| Expected Latency | 5% |
| Preference/Remaining Capacity | 8% |

---

## 🔨 7. Multi-Agent Deliberation

| Function | Description |
|---|---|
| **Create Case** | Define question, trigger, criteria → auto-build diverse panel |
| **Panel Builder** | Maximizes provider/model diversity, enforces concentration limits |
| **Role Assignment** | 8 roles: PROPOSER, ALTERNATIVE_PROPOSER, DOMAIN_ANALYST, ASSUMPTION_CHALLENGER, EVIDENCE_CHECKER, RISK_ANALYST, RED_TEAM, INDEPENDENT_JUDGE |
| **Independent First-Pass** | Members submit answers without seeing peers (immutable) |
| **Blind Critique** | Anonymized review — identities hidden, order randomized |
| **Structured Answer Contract** | Conclusion, claims, evidence, assumptions, uncertainties, confidence |
| **Revision Protocol** | Must cite new evidence or valid critique for any opinion change |
| **Dissent Preservation** | Minority reports never deleted on majority decision |
| **Diversity Snapshots** | Metrics at each stage: conclusion diversity, provider concentration, disagreement rate |
| **Conformity Detection** | Flags unsupported majority-following |
| **Decision Outcomes** | SUPPORTED_AGREEMENT, MAJORITY_WITH_DISSENT, UNRESOLVED, INSUFFICIENT_EVIDENCE |

---

## 📄 8. Intake & Decomposition Engine

| Function | Description |
|---|---|
| **Text Parsing** | Accepts free text, numbered lists, markdown, paragraphs |
| **Decomposition** | 3-strategy engine: numbered lists → paragraphs → sentence splitting |
| **Complexity Analysis** | 5 dimensions: structural, domain, integration, data, uncertainty |
| **Effort Estimation** | Function-point-inspired: complexity → FP → person-days × team factor |
| **Similarity Detection** | Jaccard + Cosine token similarity, pairwise comparison |
| **Risk Forecasting** | 6 risk categories with probability × impact scoring |
| **Module Distribution** | Auto-assigns to CONDUCTOR, PM_AGAIN, QA_AGAIN, or DEV |
| **Session History** | All intake sessions preserved and queryable |

### Risk Categories Detected:

| Category | Pattern Examples |
|---|---|
| Schedule | deadline, tight, urgent, milestone, release |
| Technical | new technology, experimental, prototype |
| Dependency | depends on, blocked by, external team |
| Resource | specialized, expert, single point |
| Quality | high volume, data migration, compliance, audit |
| Deployment | big bang, cutover, go-live |

---

## ✨ 9. Golden Flow

| Function | Description |
|---|---|
| **One-Click Trigger** | Vision → Requirements → Decompose → Analyze → Risk → Deliberation Ready |
| **AI-Powered Decompose** | Uses AUTO Router to call best AI resource for smarter decomposition |
| **Step Tracking** | Each step recorded with counts and results |
| **Summary** | Total functions, person-days, risk level in one line |

---

## ☁️ 10. Cloudflare R2 Storage

| Function | Description |
|---|---|
| **Pre-signed Upload URLs** | Short-lived S3-compatible upload URLs |
| **Pre-signed Download URLs** | Authorized temporary download access |
| **Direct Upload** | Bytes → R2 via boto3 |
| **Object Key Namespacing** | `projects/{slug}/{category}/{timestamp}_{filename}` |
| **Storage Status** | Check R2 availability |

---

## 🧪 11. Testing

| Test Suite | Type | Count |
|---|---|---|
| `test_smoke.py` | Standalone integration | 20 tests |
| `tests/test_auth.py` | Pytest | 8 tests |
| `tests/test_projects.py` | Pytest | 9 tests |
| `tests/test_ai_resources.py` | Pytest | 6 tests |
| `tests/test_skills.py` | Pytest | 8 tests |
| `tests/test_deliberation.py` | Pytest | 4 tests |
| `tests/test_intake.py` | Pytest | 5 tests |
| `tests/test_golden_flow.py` | Pytest | 3 tests |
| **Total** | | **63 tests** |

---

## 📊 Endpoint Summary

| Router | Prefix | Endpoints |
|---|---|---|
| Auth | `/api/auth` | 5 |
| Projects | `/api` | 7 |
| AI Resources | `/api/ai` | 16 |
| Skills | `/api/skills` | 11 |
| Intake | `/api/{slug}/intake` | 3 |
| Deliberation | `/api/deliberation` | 8 |
| Golden Flow | `/api/{slug}/golden` | 5 |
| Health | `/api/health` | 1 |
| **Total** | | **56** |

---

## 🎨 Frontend Pages

| Tab | Component | Features |
|---|---|---|
| 📊 Dashboard | `ProjectDashboard` | Live stats, Vision preview, Golden Flow, Requirements preview |
| 📖 Vision | `VisionPage` | Timeline, compare, new revision |
| 🛡️ Requirements | `RequirementsPage` | CRUD, search, filter, sort, stats |
| ⚡ Skills | `SkillsPage` | Catalog, versions, AUTO router test |
| 🌐 AI Resources | `AIResourcesPage` | 5 sub-tabs, providers, accounts, health check, test |
| 🔨 Deliberation | `DeliberationPage` | Case list, detail, submissions, dissent, decide |
| 📄 Intake | `IntakePage` | Text input, session list, functions, similarity, risk |

---

## 🔧 Tech Stack Details

| Component | Technology | Version |
|---|---|---|
| Backend Framework | FastAPI | 0.115.0 |
| ASGI Server | Uvicorn | 0.30.6 |
| ORM | SQLAlchemy | 2.0.35 |
| Validation | Pydantic | 2.9.2 |
| Auth | PyJWT + bcrypt | 2.9.0 / 4.2.0 |
| Rate Limiting | slowapi | 0.1.9 |
| R2/S3 | boto3 | 1.35.49 |
| Encryption | cryptography (Fernet) | 43.0.1 |
| HTTP Client | httpx | 0.27.2 |
| Frontend | React + Vite | 19.2.7 / 8.1.1 |
| Styling | Tailwind CSS | 4.3.3 |
| Icons | lucide-react | 1.28.0 |
| Toast | sonner | 2.0.7 |
| Router | react-router-dom | 7.18.1 |
| HTTP Client | axios | 1.18.1 |
| PWA | vite-plugin-pwa | 1.3.0 |
