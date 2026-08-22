# OIDA 1.0 Production Baseline

## 1. Release Identity

| Field | Value |
| --- | --- |
| Product release | OIDA 1.0 Production Baseline |
| Starting accepted head | `9f7a505fde9782d8ce370d9a0ea0fc038b24118b` |
| Product implementation | `ef3429867c7efa6fb44f94edfe20a0be0932723c` |
| Branch | `main` |
| R19 status | `ACCEPTED_WITH_OPERATIONAL_GAPS` |
| Product readiness | `READY_WITH_ISOLATED_OPERATIONAL_GAPS` |
| Remaining P0 / P1 | 0 / 0 |
| Real project | True Cloud Migration (`prj_853bcc5700a54c8db170`) |
| CI | run `32569954808`, success for starting head |

This pass changes no product source. It freezes the accepted product, deployment, recovery knowledge, and regression boundaries.

## 2. Product Definition

OIDA is an AI-ready, human-led project operating workspace. It provides one authorized view across bounded project services, versioned document governance, evidence-grounded review, change-to-resolution orchestration, daily and portfolio attention, and optional grounded AI. It is a composition and controlled initiation layer—not a replacement database for PM, QA, or Infra.

## 3. Product Principles

- AI-ready, human-led; truth before intelligence; deterministic before AI.
- Projection is not ownership.
- `EMPTY != FAILURE`; `UNBOUND != INVALID`; `UNKNOWN != ZERO`.
- `TEST != INTERNAL != CUSTOMER`.
- Action succeeded is not impact resolved; resolution is not customer acceptance.
- AI may explain and suggest; it may not approve, acknowledge, accept, sign, waive, resolve, or execute.
- Governance is flexible and policy-driven, not a universal hard lock.
- Signed and baselined versions remain immutable.

## 4. Authority Model

| Authority | Owns |
| --- | --- |
| Account Again | human/service identity, authentication, tenant/access claims |
| Document Again | requirements, clarifications, assumptions, decisions, change requests, documents, lifecycle, governance, acceptance evidence |
| PM Again | planning, schedule, milestones, dependencies, effort, PM delivery state |
| QA Again | tests, execution, defects, QA evidence and readiness |
| Infra Again | architecture, environments, components, connections and Infra readiness |
| Conductor Again | orchestration and bounded workflow relay |
| OIDA | authorized composition, deterministic projection, project intelligence, human-confirmed orchestration context, controlled owner-action initiation and per-user workspace checkpoints |

**OIDA DOES NOT OWN PM/QA/INFRA DOMAIN TRUTH.** It does not query bounded databases directly or persist shadow copies as authority.

## 5. Capability Summary

The canonical inventory is [OIDA-1.0-CAPABILITY-REGISTRY.csv](OIDA-1.0-CAPABILITY-REGISTRY.csv). It freezes Project/Identity, Document Governance, Project Truth/Attention, Reviewer/AI Reviewer, Change/Impact, Human Confirmation, Controlled Actions, Resolution/Resolution Intelligence, Command Center/Daily Briefing, Portfolio, Copilots, Governance/Acceptance, and Audit/Provenance.

Production status `DETERMINISTIC_FALLBACK_PRODUCTION` means the feature is useful without an AI provider and does not imply a configured production model.

## 6. Core Contracts

| Contract | Purpose | Authority sources | Mutability | Main consumers |
| --- | --- | --- | --- | --- |
| `project_bindings/v1` | explicit service correlation | authorized human selections | human write | Project Truth and owner links |
| `project_truth/v1` | normalized PM/QA/Infra snapshot | bounded owner APIs | read-only | Attention, precheck, Command Center |
| `project_attention/v1` | explainable current attention | Project Truth and deterministic rules | read-only | Command Center, briefings |
| `reviewer_evidence/v1` | version/evidence packet | Document evidence and recorded owner snapshots | read-only | Reviewer and AI Reviewer |
| `reviewer_change_brief/v1` | deterministic comparison | reviewer evidence | read-only | Deliverables reviewer |
| `ai_reviewer_brief/v1` | grounded reviewer advice | cited reviewer evidence | read-only | Reviewer UI |
| `project_change/v1` | typed recorded change | Document/owner revisions | read-only | Impact Intelligence |
| `impact_relationships/v1` | typed one-hop links | recorded structure or advisory AI | read-only | impact candidates |
| `impact_candidates/v1` | review recommendations | relationships and deterministic rules | read-only | confirmation UI |
| `impact_confirmation/v1` | human relationship decision | authenticated actor and evidence hash | append/write | action routing |
| `impact_actions/v1` | safe action recommendations | deterministic allowlist | read-only | Deliverables |
| `action_route/v1` | preview/execute/result history | human decision plus owner API | controlled write | Resolution |
| `impact_resolution/v1` | evidence-based state | refreshed owner truth and rules | evaluate/write history | Resolution Intelligence |
| `resolution_intelligence/v1` | why unresolved and safe next step | impact resolution registry | read-only | Command Center/briefings |
| `resolution_intelligence_ai/v1` | grounded explanation | cited resolution packet | read-only | assistant API |
| `project_command_center/v1` | project operating view | authorized composed truth | read-only | Project Home |
| `project_copilot/v1` | grounded project advice | Command Center evidence | read-only | Project Home |
| `project_briefing/v1` | first/since-review briefing | Command Center and checkpoint | read-only | Project Home |
| `project_review_checkpoint/v1` | per-user reviewed-through cursor | explicit authenticated acknowledgement | idempotent write | Daily Briefing |
| `project_briefing_ai/v1` | grounded briefing advice | bounded briefing packet | read-only | briefing API |
| `portfolio_command_center/v1` | authorized project summaries | project centers/briefings | read-only | Projects page |
| `portfolio_briefing/v1` | cross-project review packet | authorized summaries and checkpoint | read-only | Projects page |
| `portfolio_review_checkpoint/v1` | independent portfolio cursor | explicit authenticated acknowledgement | idempotent write | Portfolio |
| `portfolio_copilot/v1` | scoped grounded portfolio advice | project-prefixed evidence | read-only | Portfolio Copilot |

Supporting registries are `impact_action_registry/v1`, `impact_resolution_rules/v1`, and internal `project_command_context/v1`; they are not additional owner authorities.

## 7. Closed-Loop Architecture

```text
OWNER APIs → PROJECT TRUTH → PROJECT ATTENTION → CHANGE → IMPACT
                                                       ↓
                                             HUMAN CONFIRMATION
                                                       ↓
                                         HUMAN PREVIEW + EXECUTE
                                                       ↓
                                  PM/QA OWNER API → OWNER RESULT
                                                       ↓
                     FRESH OWNER TRUTH → RESOLUTION → RESOLUTION INTELLIGENCE
                                                       ↓
                           COMMAND CENTER → DAILY / PORTFOLIO BRIEFING
                                                       ↓
                                  OPTIONAL GROUNDED, CITED AI
```

Humans own confirmation, execution, review, approval, acknowledgement, acceptance, sign-off, and waiver decisions. PM/QA/Infra remain authoritative after an action. OIDA owns only its orchestration records and derived read models.

## 8. AI Boundary

AI Reviewer, Project Copilot, Portfolio Copilot, Resolution Assistant, and Daily Briefing AI consume bounded deterministic evidence. Material factual claims require citations. Unknown citations/actions, unsupported resolution, time-window, authority, and customer-acceptance claims fail closed. Evidence is treated as untrusted data to resist prompt injection. Provider absence/failure returns deterministic content. Auto-execution and AI authority are zero.

## 9. Persistence Model

OIDA/Document-owned 1.0 orchestration/workspace tables are:

| Table | Classification | Purpose |
| --- | --- | --- |
| `impact_confirmations` | orchestration/audit evidence | immutable human relationship decisions |
| `impact_action_routes` | orchestration state | requested allowlisted owner action and result |
| `impact_action_events` | audit/evidence | action lifecycle events |
| `impact_resolutions` | derived orchestration state | current deterministic resolution projection |
| `impact_resolution_events` | audit/evidence | immutable resolution transitions/reopens |
| `project_review_checkpoints` | user workspace state | per-user/project review cursor |
| `portfolio_review_checkpoints` | user workspace state | independent per-user portfolio cursor |

Document governance also persists versioned deliverables, signoffs, gate resolutions, and audit events under Document Again authority. No PM/QA/Infra shadow domain database exists in OIDA.

## 10. Production Deployment

| Component | Platform/app | Release/image or deployment | Health |
| --- | --- | --- | --- |
| OIDA Web | Cloudflare Pages `oida`; `oida.kanphong.com` | `c56491ef-a48a-4db8-a152-8f56834b98fb`; source `ef34298`; `index-DfgOg1Ze.js`, `index-CiWTekrW.css` | custom domain HTTP 200 via browser/curl user agent |
| Gateway | Fly `oida-gateway`; `api-oida.kanphong.com` | release 8; `deployment-01M0KHJHVHKMQRRPP1SC1FHQX0` | 1/1 passing; `/healthz` 200 |
| Document Again | Fly `oida-document` | release 31; `deployment-01M0MK0ZTGMTDQ2QF8ANENNSMT` | 1/1 passing; `/api/health` 200 |
| PM Again | Fly `oida-pm` | release 9; `deployment-01M06PDGAMYJZFWAB5BZP1998A` | 1/1 passing; `/api/health` 200 |
| QA Again | Fly `oida-qa` | release 9; `deployment-01M06PF55XB3VKDGHD07G6RNE3` | 1/1 passing; `/api/health` 200 |
| Account Again | Fly `oida-account` | release 8; `deployment-01M06YEC6JQV9Z41MBQ8FESER7` | 1/1 passing; `/api/v1/health` 200 |
| Conductor Again | Fly `oida-conductor` | release 8; `deployment-01M06PGR3RS0XEQVW95NQKQC1G` | 1/1 passing; `/api/health` 200 |
| Infra Again | Fly `oida-infra` | release 7; `deployment-01M06NNYBMQMW92Y7KQW5JK381` | 1/1 passing; `/health` 200 |

The browser-facing production revision maps exactly to implementation `ef34298`. Document source-to-image mapping is proven by the R19 deployment log and deployed-runtime re-dogfood, not an embedded Git label. Other service releases are verified runtime inventory and were not rebuilt during this freeze.

## 11. Test / CI Baseline

| Category | Frozen evidence |
| --- | --- |
| Document/backend | 214 passed |
| Required R19 cross-flow | 3 passed |
| Focused reviewer/action/resolution/briefing/portfolio/center | 60 passed |
| Truth | accepted project-truth suites plus real-project comparison |
| Reviewer / AI safety | 24 focused passed within final suite |
| Impact / confirmation | included in 214 and golden scenarios |
| Action / resolution | included in 214 and golden closed loop |
| Command Center / briefing / portfolio | included in 60 focused and 214 full |
| Authorization/security | tenant isolation and fail-closed gateway evidence |
| Frontend | 12 passed |
| Gateway | 3 passed |
| Lint | pass with known pre-existing warnings |
| Production build | pass with known bundle-size advisory |
| CI | run `32569954808` success for `9f7a505` |

## 12. Golden Scenarios

1. Closed loop: change → UNKNOWN impact → human confirmation → ready preview → human execute → QA owner result → truth refresh → incomplete QA evidence → `WAITING_ON_OWNER` → Resolution Intelligence missing-evidence explanation → Daily Briefing waiting. Future tests must keep successful action separate from resolution and acceptance.
2. Document review: Project Truth → readiness precheck → versioned document → reviewer evidence → deterministic change brief → explicit human decision. A source revision yields `POTENTIALLY_STALE`; prior hash remains immutable; REVIEW language grants no approval; TEST remains non-customer.
3. Portfolio: authorized projects → bounded summaries → explainable P1–P5 priority → portfolio briefing/checkpoint → grounded project-prefixed Copilot citations. Unauthorized projects are absent; portfolio checkpoint never advances project checkpoints; checkpoint races retain late evidence.

## 13. Security / Governance Guarantees

- Gateway and services fail closed; client-supplied identity headers are stripped and re-derived.
- Tenant/project guards and authorized-scope-first Portfolio composition prevent cross-project disclosure.
- Owner mutations require current evidence, explicit human preview/execute, allowlist, authorization, idempotency, owner API, and reconciliation.
- Audit and provenance preserve actor, origin class, evidence hash, owner result, and state transitions.
- TEST/INTERNAL evidence cannot become CUSTOMER acceptance; action/resolution never imply acceptance.
- Signed/baselined revisions remain immutable; new work creates a revision.
- Flexible governance preserves Proceed With Risk, Policy Exception/Waiver, and Not Applicable rather than imposing a universal lock.

## 14. Known Limitations

- Production AI provider is optional and currently not configured.
- Selected authenticated browser, multi-device checkpoint, and safe mutation dogfood remain incomplete.
- Infra can legitimately be UNBOUND; some owner APIs do not expose useful freshness timestamps.
- QA evidence classification is intentionally bounded by available owner contracts.
- Only two low-risk PM/QA owner routes exist; no high-risk Infra mutation.
- No autonomous remediation, scheduled notification, resource/financial optimization, or automatic customer acceptance.
- Portfolio production dogfood currently has one active eligible project; scale/isolation use deterministic fixtures.
- The narrow-screen fixed sidebar remains verified non-P0/P1 friction.

## 15. Operational Backlog

- AUTH / DOGFOOD: authenticated browser replay, multi-device checkpoint validation, safe disposable owner-action dogfood, genuine multi-project Portfolio dogfood.
- AI PROVIDER: authorized provider configuration, production smoke test, authorized-evidence compatibility run.
- SSO / NAVIGATION: owner deep-link SSO continuity and stable specialist routes where still missing.
- UX / OPERATIONS: narrow-screen sidebar and other verified P2/P3 friction only.

## 16. Do-Not-Regress Checklist

- [ ] No bounded-service truth duplication or direct cross-service DB access.
- [ ] No name/slug-inferred binding.
- [ ] EMPTY remains distinct from failure; UNBOUND from INVALID; UNKNOWN from zero.
- [ ] TEST and INTERNAL remain distinct from CUSTOMER.
- [ ] Signed/baselined versions remain immutable.
- [ ] AI material claims remain grounded/cited and AI never executes or decides.
- [ ] Human confirmation never becomes owner truth.
- [ ] Owner actions use owner APIs only with preview, authorization and reconciliation.
- [ ] Action success never implies resolution; resolution never implies acceptance.
- [ ] Portfolio never exposes unauthorized projects.
- [ ] Project and portfolio checkpoints remain race-safe and independent.
- [ ] Degraded/partial truth remains visible rather than false-green.

## 17. Future Development Rule

After OIDA 1.0, new phases require at least one of: real user friction, real project dogfood evidence, a clear high-value product goal, an operational requirement, or a security/governance requirement. P0 fixes immediately; P1 before material expansion; P2 is prioritized backlog; P3 is polish backlog. Do not destabilize the baseline for theoretical cleanup.

## 18. Final Acceptance

```text
PRODUCT_RELEASE=OIDA_1_0
SOURCE_CODE_CHANGED=NO
REAL_PROJECT_DOGFOOD=PROVEN
GOLDEN_CLOSED_LOOP=PROVEN
PRODUCTION_DEPLOYED=PASS
P0_REMAINING=0
P1_REMAINING=0
AUTHORITY_BOUNDARIES=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS
SIGNED_VERSION_IMMUTABILITY=PASS
OPERATIONAL_GAPS=ISOLATED_AND_DOCUMENTED
RELEASE_BASELINE=ACCEPTED
NEXT_STEP=STOP_AND_USE_PRODUCT
```
