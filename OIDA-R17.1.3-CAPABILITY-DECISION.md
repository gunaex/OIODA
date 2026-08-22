# OIDA R17.1.3 — Capability Projection Decision

Date: 2026-08-22 (Asia/Bangkok)  
Baseline: `d73f3604384faa2ecf96d655e9a877640aea39e1`  
Decision matrix: `OIDA-R17.1.3-CAPABILITY-DECISION-MATRIX.csv`

## 1. Executive Decision

OIDA should become the place where a project participant understands delivery health, sees cross-service blockers, and reaches the next relevant specialist context. It should not reproduce the planning, test-execution, or infrastructure-authoring workbenches.

The canonical inventory contains 110 concrete owner capabilities. Fifty-six are useful read projections, four are bounded lightweight actions worth retaining or considering, forty belong in owner applications, nine are internal mechanics, and one AI-assisted architecture capability is explicitly deferred. The proposed implementation slice is ten high-value projections, no new write action, and contextual owner deep links. Existing bounded writes remain owned and persisted by PM Again or QA Again.

| Service | Total Capabilities | A Project | B Action | C Delegate | D Internal | E Future |
|---|---:|---:|---:|---:|---:|---:|
| PM Again | 35 | 17 | 2 | 16 | 0 | 0 |
| QA Again | 35 | 16 | 2 | 14 | 3 | 0 |
| Infra Again | 40 | 23 | 0 | 10 | 6 | 1 |
| **TOTAL** | **110** | **56** | **4** | **40** | **9** | **1** |

## 2. Decision Principles

The matrix applies the following factors explicitly: project visibility, frequency, cross-service relevance, decision impact, workload reduction, complexity, write sensitivity, owner specialization, governance value, and relevance to Overview, Precheck, and Acceptance.

The decisive rules are:

1. Project state and exceptions are projected; specialist registers are not copied.
2. A read model does not transfer authority. Every projected fact keeps its owner ID, revision where available, retrieval state, and honest unavailable/unauthorized semantics.
3. OIDA may offer a write only when the action is small, frequent, understandable, supported by an owner API, and still persists exclusively in that owner.
4. Detailed editors, bulk operations, destructive execution, evidence custody, and governed owner approvals stay in the owner application.
5. Overview remains executive: current position, next material event, blockers, and required attention. Detail belongs in Planning, QA, Architecture, Precheck, or an owner deep link.
6. `DATA_AVAILABLE`, `UI_AVAILABLE`, and `ACTION_AVAILABLE` are separate decisions. A fact in `project_truth/v1` is not automatically a usable projection.
7. `FUTURE` is used only once: Infra AI-assisted architecture work requires a separate intelligence and governance decision.

Role recommendations reuse existing project/governance vocabulary: `PROJECT_OWNER`, `PM`, `QA`, `INFRA`, `ARCHITECT`, `REVIEWER`, `APPROVER`, `CUSTOMER_TECHNICAL_OWNER`, and the existing specialist roles such as `SECURITY_LEAD`. “FYI” in the matrix means visibility, not permission to act.

## 3. PM Again Decisions

Project into OIDA the PM answers that determine overall delivery: health, schedule, next milestone, dependency blockers, task attention, plan-versus-actual variance, slippage, workstream progress, effort/budget variance, capacity pressure, PM risks/issues, handoff state, and project activity.

Retain the existing bounded actions to update task progress and create a lightweight PM risk/issue. Both have supported owner write APIs and already persist to PM Again. They should be role-gated and surfaced contextually; they must not become an OIDA task or board register.

Delegate project administration, workstream/task authoring, Gantt editing, annotations, actual overrides, estimation configuration, resource allocation, knowledge pages, whiteboards, report catalogs, PM change requests, PM document workflow, working-calendar configuration, and bulk import/export. These operations are either editor-heavy, infrequent, write-sensitive, or liable to duplicate Document Again governance.

PM’s most important projection gaps are next-milestone attention, dependency blockers, and slippage. The current truth provides schedule/milestone/dependency aggregates but does not yet answer “what is late?” or “what matters next?”

## 4. QA Again Decisions

Project QA scope, suite/test-definition state, current published revision, coverage, cycle status, remaining and failed tests, readiness, evidence completeness/provenance, open and blocking defects, QA sign-off class/status, automation outcome, and orchestrated request/result status.

Retain defect creation as a bounded OIDA action. A QA rerun is also technically suitable for Class B because the owner exposes a supported rerun API, but it is P2 and should not enter the first slice until OIDA can show the prior attempt, reason, idempotency/correlation context, and confirmation.

Delegate suite/case/step authoring, revision publishing, cycle control, manual execution, result review, evidence upload/annotation/archive, defect workflow administration, cycle sign-off, hybrid-run control, manual checkpoint decisions, reports, and exports. Runner tokens, lease/event/recorder state, variables, and storage quotas are internal/admin-only.

QA’s highest-value gaps are failed-test attention, evidence completeness and provenance, and QA sign-off status. QA sign-off must remain labeled TEST/INTERNAL evidence and must never be presented as Document Again customer acceptance.

## 5. Infra Again Decisions

Project whether architecture exists, its accepted state and revision, the relevant graph/components/connections, critical network/port/security exceptions, environment readiness, feasibility, implementation-plan readiness, dependencies and gates, handoff status, execution/preflight state, verification evidence, promotion/rollback/UAT status, and scoped production readiness.

No new Infra write belongs in OIDA in this phase. Architecture editing, design generation, simulation execution, design acceptance/change requests, implementation approval, package execution/reconciliation, promotion, rollback, and UAT sign-off all require specialist context or carry high/critical write risk. OIDA should show their state and offer contextual navigation.

Workspace pointers, provider-catalog synchronization, runner mechanics, sandbox execution, raw control-plane operations, and liveness/capability metadata are internal only. Provider/service comparison is useful but remains delegated specialist architecture work. AI-assisted generation/review is deferred to a future intelligence phase.

Infra projections must be scoped by an explicit project-to-Infra workspace/design binding. A global production-readiness response is insufficient for project truth. An explicit `UNBOUND` remains honest and must render as unknown/unavailable, never as ready or empty.

## 6. Cross-Service Opportunities

| Opportunity | Combined owner signals | Recommendation |
|---|---|---|
| Go-live readiness | PM next milestone/schedule + QA readiness/blocking defects/evidence/sign-off + Infra environment/connectivity/production readiness/rollback | **R17.1.3** as a compact read-only Project Health composition; no new acceptance decision |
| Delivery attention | PM late tasks/dependencies + QA failed tests + Infra blocked implementation gates/preflight | **R17.1.3** as prioritized source-linked attention items |
| Acceptance evidence readiness | QA evidence/sign-off + Infra UAT/execution evidence + Document governance requirements | **R17.1.3** in Document Precheck; preserve Document as acceptance authority |
| Delivery impact | PM schedule change + QA execution state + Infra dependency/gate state | **Future intelligence phase**; requires correlation and change semantics beyond current summaries |
| What changed | PM activity + QA revision/result history + Infra revision/run/promotion history | **Future intelligence phase** after stable source event contracts |
| Cross-service My Actions | Owner-assigned PM tasks + QA reviews/defects + Infra gated approvals | **Future workflow slice**; role/action assignment contract is not yet uniform |

These are `CROSS_SERVICE_OPPORTUNITY` items, not new bounded truth. OIDA composes the view; PM, QA, Infra, and Document remain authoritative.

## 7. Recommended OIDA Surfaces

```text
OIDA Project Workspace
├── Overview
│   ├── Delivery Health: schedule, next milestone, slippage
│   ├── QA Readiness: remaining/failed tests, blocking defects, evidence
│   ├── Infra Readiness: revision, environments, connectivity, implementation gates
│   └── Governance / Acceptance: Document state plus source evidence readiness
├── Project Delivery / Planning
│   ├── Workstreams and task attention
│   ├── Dependencies and plan-versus-actual
│   └── Effort and budget variance
├── QA / Readiness
│   ├── Scope, coverage, cycles and failures
│   ├── Defects and evidence provenance
│   └── Open in QA Again
├── Architecture / Infra
│   ├── Read-only design and environment projection
│   ├── Feasibility, gates, preflight and readiness
│   └── Open in Infra Again
├── Documents
│   ├── Deliverables
│   ├── Cross-service Precheck
│   └── Acceptance owned by Document Again
└── My Actions
    ├── Existing review / approval / sign-off
    ├── Selected bounded PM/QA actions
    └── Owner deep links for specialist work
```

Overview should contain at most the compact health/attention summaries. It should not contain task, defect, environment, port, or execution registers.

## 8. Actions Worth Bringing Into OIDA

| Action | Owner API | Current OIDA action | Decision |
|---|---|---|---|
| Update PM task progress/status | `PUT /api/{slug}/tasks/{id}` | Present | Retain as Class B; role-gate and keep PM ownership |
| Create lightweight PM risk/issue | `POST /api/{slug}/board-items` | Present | Retain as Class B; concise form only |
| Create QA defect from project/test context | `POST /api/{slug}/defects` | Present | Retain as Class B; pass owner entity references |
| Request QA rerun | `POST /api/qa-requests/{id}/rerun` | Missing | Class B/P2; owner API exists, defer until attempt/correlation context is visible |

`OWNER_ACTION_API=YES` for every Class B item. No duplicate OIDA write model is recommended. The first implementation slice adds zero new write actions; it may consolidate the three existing actions into contextual attention/My Actions affordances.

## 9. Functions That Must Stay In Owner Apps

PM Again retains full project/workstream/task/Gantt/resource/estimate editors, bulk data operations, PM reports, notes/whiteboards, PM CRs, and PM document workflow.

QA Again retains suite/case/step/revision authoring, manual and hybrid execution, cycle/result review, evidence custody and annotation, detailed defect workflow, QA sign-off entry, runner/recorder controls, and exports.

Infra Again retains architecture/topology authoring, simulation execution, provider selection, plan approval, execution-package control, promotions, rollback execution, Infra UAT sign-off, and all runner/sandbox/control-plane operations.

For Class C, owner project/entity routes and bound IDs generally exist, so contextual deep linking is feasible. However, standalone frontend route conventions and browser auth continuity must be contract-tested before implementation. Until then, “Deep Link Possible=YES” means the context can be resolved, not that seamless SSO navigation is already production-proven.

## 10. Current OIDA Gaps

The matrix identifies 13 P0 Class A/B capabilities whose UI is partial or missing and 16 equivalent P1 gaps. This is the candidate pool, not the implementation scope.

The most consequential P0 gaps are:

- PM next milestone, dependency blockers, and slippage attention.
- QA failed-test reasons, evidence completeness/provenance, and QA sign-off status.
- Infra revision/feasibility, implementation dependencies/readiness, preflight blockers, and project-scoped production readiness.

Important P1 gaps include PM plan-versus-actual and handoff state; QA evidence items and request/result state; and Infra work packages, execution evidence, promotion, rollback, UAT, and cross-service handoff status.

Some are projection gaps rather than integration gaps. For example, QA blocking-defect count is `DATA_AVAILABLE=YES` and `UI_AVAILABLE=PRESENT`, while QA evidence item provenance is only partially available to OIDA and `UI_AVAILABLE=MISSING`. Infra implementation readiness has an owner read API but is not currently in `project_truth/v1` or the UI.

## 11. Proposed R17.1.3 Implementation Scope

Implement one curated, read-first Project Health/Attention slice using additive `project_truth/v1` fields and owner provenance:

1. PM next critical milestone and late/slipping attention.
2. PM blocked dependency summary with source-linked drill-down.
3. PM effort/budget variance summary.
4. QA remaining/failed-test attention by explicit QA scope.
5. QA blocking-defect attention with contextual owner links.
6. QA evidence completeness and QA sign-off status, explicitly labeled TEST/INTERNAL.
7. Infra current revision and feasibility exceptions.
8. Infra environment/connectivity readiness exceptions.
9. Infra implementation readiness, dependencies, and blocking gates.
10. Infra preflight/scoped production-readiness exceptions when an explicit workspace/design binding exists.

Place only compact summaries on Overview. Put explanations in Project Delivery, QA Readiness, Architecture, and Document Precheck. Add contextual owner deep links where route/auth contracts pass validation. Add no new database, register, AI feature, governance system, or write action.

This slice is intentionally smaller than the P0/P1 candidate pool. It answers “where are we, what matters now, and what is blocked?” without importing specialist workbenches.

## 12. Explicitly Deferred Scope

- Full PM task management, Gantt editing, resource planning, estimates/configuration, bulk import/export, and knowledge tools.
- Full QA authoring, manual/hybrid execution workspace, runner/recorder controls, detailed evidence annotation, sign-off entry, and exports.
- Infra architecture/resource/network editors, simulation controls, plan/execution/promotion/rollback/UAT actions, provider catalog administration, and runners.
- QA rerun action until prior-attempt and correlation context is visible.
- Cross-service action assignment/My Actions expansion until owner role and assignee semantics are normalized.
- AI review briefs, change-impact intelligence, risk summaries, and What Changed intelligence.
- Any inferred go-live or customer-acceptance decision. OIDA may present evidence readiness; humans and Document Again governance decide acceptance.

## 13. Risks

- Over-projection can turn Overview into an unreadable specialist dashboard. Mitigation: exception-first summaries and drill-down surfaces.
- Owner APIs do not all provide project-scoped summary endpoints or source timestamps. Mitigation: honest `UNKNOWN` freshness and explicit binding/scope requirements.
- Infra production readiness is currently global unless linked through an owner workspace. Mitigation: do not project it as project truth without explicit scope.
- Deep links may lose context or require another login. Mitigation: validate frontend route contracts and Account identity continuity before release.
- Existing PM/QA pages still contain some empty-on-error behavior outside `project_truth/v1`. Mitigation: consume the shared truth layer for critical signals and preserve owner failure states.
- QA sign-off, Infra UAT, and execution evidence can be mistaken for customer acceptance. Mitigation: display source and evidence class; Document Again remains the only acceptance authority.
- Adding many owner calls can increase latency. Mitigation: prefer owner summary endpoints, parallel source groups, explicit call budgets, and no silent retries.

## 14. Acceptance Recommendation

Accept this decision pass for human review. It answers the required product questions with a canonical owner-derived inventory, one classification per capability, action-API parity, role/surface/precheck guidance, current-state gaps, delegation boundaries, and a deliberately small implementation slice.

Do not begin implementation until a human approves the matrix and specifically confirms the ten projection capabilities, zero-new-write posture, and deep-link contract work.
