# OIDA R17.1.3 — Project Attention

Date: 2026-08-22 (Asia/Bangkok)  
Baseline: `3bdac0dad10ca4ca17ded6297df8271426ea2aad`  
Implementation commit: `323d37271786d522d9d8d522f51accfaefc80c2c`

## 1. Baseline

R17, R17.1, R17.1.1, and R17.1.2 were accepted; R17.1.2 was fully closed. The accepted R17.1.3 decision pass inventoried 110 owner capabilities and selected a small read-first projection. The implementation started from a clean `main` worktree. The existing `project_bindings/v1` and `project_truth/v1` contracts, parallel source retrieval, provenance, freshness, and independent failure states were retained.

## 2. Approved Decision Scope

This pass implements deterministic Project Attention and compact PM, QA, and Infra delivery-health projections. It introduces no owner mutation, editor, AI summary, database, assignment model, or customer-acceptance inference. Specialist resolution stays in the owner applications.

## 3. Truth Contract Changes

The change is additive and remains `project_truth/v1`. A separate truth endpoint was not created.

| Signal | Before | Classification | Additive normalized truth |
|---|---|---|---|
| PM next milestone and slippage | Gantt items already fetched | DERIVABLE | `pm.attention.next_critical_milestone`, slipping count/items |
| PM blocked dependencies | dependency IDs already fetched | DERIVABLE | blocked dependency count/items |
| PM effort budget | only estimate summary fetched | MISSING | authoritative `/effort-budget` gauge and variance fields |
| QA remaining/failed/blocked | dashboard result counts fetched | DERIVABLE | explicit current counts |
| QA evidence completeness | dashboard evidence ratio fetched | DERIVABLE | aggregate numerator, denominator, percent and state |
| QA evidence class | QA owns test evidence only | DERIVABLE/PARTIAL | TEST present/not-present; INTERNAL unknown; CUSTOMER not provided by QA |
| Infra revision/connectivity | bound design already fetched | AVAILABLE/DERIVABLE | revision plus exceptional edge count/items |
| Infra feasibility | not fetched | MISSING | bound design feasibility and blocking issues |
| Infra environment readiness | environment records lack readiness state | MISSING | `UNKNOWN` with an explicit reason |
| Infra implementation/preflight | no plan/execution-package binding | MISSING | `UNKNOWN` with explicit binding reasons |
| Infra production readiness | owner rows are global unless `designId` matches | PARTIAL | scoped row only; otherwise `UNKNOWN` with reason |

Owner retrieval increases PM from three to four calls and bound Infra from three to four calls. QA remains three calls per distinct explicit scope; repeated scope bindings are deduplicated. For the representative project, the expected fan-out changes from 18 to 19 because Infra is unbound: PM 4 + QA 15 + Infra 0.

## 4. PM Projection

The next critical milestone is selected from incomplete dated milestones, preferring overdue milestones and then the earliest upcoming date. Slippage requires both an elapsed due date and progress below 100%; progress alone is never called late. A dependency is blocked only when the dependent and its referenced prerequisite are both incomplete. Effort status and remaining man-days come directly from PM's budget gauge; man-days are never labeled as money.

## 5. QA Projection

The projection aggregates independent, distinct, explicitly bound QA project scopes. It sums current dashboard result counts and owner defect rows within those scopes. Remaining means `NOT_RUN`; failures use QA's `FAIL` value (with legacy `FAILED` compatibility); blocked tests remain separate. P0/P1 blocking-defect semantics reuse QA's actual severity contract.

Evidence state is computed from the owner numerator/denominator as `NOT_STARTED`, `COMPLETE`, `MISSING`, or `PARTIAL`. QA evidence is explicitly classified as TEST evidence. INTERNAL evidence is `UNKNOWN`, and CUSTOMER evidence is `NOT_PROVIDED_BY_QA`; no QA result becomes customer acceptance.

## 6. Infra Projection

For an explicitly bound design, OIDA projects its revision, material feasibility blockers, and exceptional connectivity edges. Environment, implementation-plan, and preflight readiness stay `UNKNOWN` where owner records or explicit bindings do not support a project-scoped conclusion. Global production-readiness rows are not attributed to a project unless their `designId` matches. An unbound Infra source remains `UNBOUND`, never zero or ready.

## 7. Project Attention Composition

`project_attention/v1` is a deterministic projection embedded in `project_truth/v1`. Explicit priority order is BLOCKER, ISSUE, UNVERIFIED, INFO; there is no score or threshold model. Failed/blocked QA results, blocking defects, blocked PM dependencies, and Infra feasibility/connectivity failures are blockers. Overdue PM work, owner-declared effort warnings, remaining tests, and evidence gaps are issues. Source failure, unknown readiness, and unbound domains are unverified. Top-level blocker, issue, and unverified counts remain separate.

| Attention Item | Domain | Owner Fact | Normalized Truth | Display Result | Priority |
|---|---|---|---|---|---|
| Blocked dependency | PM | incomplete dependency IDs in Gantt | `blocked_dependency_count` | blocked dependency count | BLOCKER |
| Slipping delivery | PM | incomplete item with elapsed end date | `slipping_item_count` | overdue item count | ISSUE |
| Effort variance | PM | effort-budget status | `effort_variance` | status and remaining MD | ISSUE when owner warns |
| Failed/blocked tests | QA | current dashboard result counts | failed and blocked counts | combined attention fact; separate card counts | BLOCKER |
| Blocking defects | QA | open P0/P1 defects | `blocking_defect_count` | blocking defect count | BLOCKER |
| Remaining tests | QA | current `NOT_RUN` count | `remaining_test_count` | not-run count | ISSUE |
| Evidence gap | QA | evidence ratio | evidence state/completeness | state and percent | ISSUE |
| Feasibility exception | Infra | owner `blockingIssues` | exception count/items | exception count | BLOCKER |
| Connectivity exception | Infra | exceptional design edge state | exception count/items | exception count | BLOCKER |
| Unknown readiness | Infra | absent scoped readiness/binding | explicit `UNKNOWN` and reason | unverified state | UNVERIFIED |
| Owner source failure/unbound | All | source status | independent source status | source-specific state | UNVERIFIED |

## 8. Go-Live Readiness

`DEFERRED`. Current governance and domain bindings are not sufficiently mature for an explainable cross-service go-live decision. In particular, Infra implementation/preflight is not explicitly bound and TEST evidence is not INTERNAL or CUSTOMER acceptance. Deferral is safer than a misleading executive status and does not create a project lock.

## 9. Owner Deep Links

Deep-link construction is isolated in `ownerLinks.js`. It requires an HTTPS base without credentials, an explicit bound owner ID, a known entity route, and an explicit `VITE_OWNER_AUTH_CONTINUITY=true` assertion. PM and QA route contracts are known and URL-encoded. Infra has no stable URL route accepting a design ID. Production auth continuity is not proven: PM Again and QA Again use separate HTTP-only application cookies, while OIDA uses its Account token in local storage. Consequently no owner URL is fabricated and the UI displays `Owner deep link unavailable`. Internal OIDA planning, QA, and Infra drill-down links remain available.

## 10. UX

Project Overview now leads with a concise Project Attention card, separate blocker/issue/unverified totals, at most five prioritized facts, and responsive PM Attention, QA Readiness, and Infra Readiness sections. Source states remain visible. The former duplicate Execution and Verification cards were removed, while detailed raw cross-service truth remains available through collapsed disclosure. Status text accompanies color and icons, links are labeled, headings are semantic, and the three-column layout collapses for smaller viewports.

## 11. Tests

- Document Again: 136 passed.
- Focused truth/attention: 16 passed.
- Gateway: 3 passed.
- PM Again: 38 passed.
- QA Again: 101 passed, 5 accepted skips.
- Infra Again: the configured full suite produced 360 passed, 8 skipped, and one stale test-owned kind-cluster collision. After deleting only `ia-test-v3`, that exact test passed in isolation; all 361 tests therefore have fresh passing evidence.
- Frontend owner-link tests: 3 passed.
- Frontend lint: exit 0 with the pre-existing warning backlog; no new warning in touched code.
- Production frontend build: 1,784 modules, `index-BkWud19Q.js`, `index-DIk2aTON.css`.

Tests cover every selected supported signal, QA authoritative-empty semantics, Infra unbound semantics, independent PM unavailable/QA unauthorized/Infra invalid behavior, deterministic attention counts, and safe owner-link construction.

## 12. Browser Validation

The accepted production assets were loaded through headless Chrome at 1440×1000. The copied saved browser profile reached the OIDA sign-in page because its Account session had expired. The authenticated Overview, attention cards, responsive authenticated state, and application console/network therefore remain `BLOCKED` pending a fresh authorized Account Again login. No credential boundary was bypassed and no token was printed. The unauthenticated browser path rendered normally; Chrome emitted no application exception.

## 13. Production Validation

Document Again deployed as Fly machine version 20 using image `deployment-01M0KY8SAW1YCMP4NKNYYSWPD6`; its configured machine health check passes. Cloudflare Pages production deployment `1f73ab5f-fc9b-431d-a300-bdf6d180f2f6` reports source `323d372`, and `https://oida.kanphong.com` serves the exact accepted asset hashes. GitHub Actions run `32553821369` completed successfully for `323d372`.

The production gateway correctly rejects an unauthenticated representative-project truth request with HTTP 401. Live authenticated truth for `prj_853bcc5700a54c8db170`, production attention values, and deep-link navigation remain blocked by the expired human session. Production deployment is proven; authenticated functional acceptance is partial.

## 14. Performance

The expected representative-project call budget changes from 18 to 19: one justified PM effort-budget call, no QA increase, and no Infra call while unbound. Source groups remain parallel and there are no retries or duplicate QA scope calls. Five public production gateway documentation requests completed in 138–170 ms, but these are not project-truth measurements. Authenticated `project_truth` latency and Overview runtime remain unmeasured rather than being inferred from unrelated endpoints.

## 15. Deferred Scope

- Go-live readiness and acceptance-evidence composition until deterministic governance and domain bindings mature.
- Owner deep links until auth continuity is proven; Infra additionally needs a stable design route.
- Infra implementation/preflight facts until explicit plan and execution-package bindings exist.
- Specialist editors, full registers, assignment normalization, cross-service writes, QA rerun, AI summaries, and any new database.

## 16. Acceptance

| Service | Capability | Decision Class | R17.1.3 Status | Truth Source | OIDA Surface | Owner Link |
|---|---|---|---|---|---|---|
| PM | Next critical milestone | A | IMPLEMENTED | Gantt | Overview / PM Attention | BLOCKED auth continuity |
| PM | Slipping delivery | A | IMPLEMENTED | Gantt dates/progress | Overview / PM Attention | BLOCKED auth continuity |
| PM | Blocked dependencies | A | IMPLEMENTED | Gantt dependency IDs | Overview / PM Attention | BLOCKED auth continuity |
| PM | Effort budget variance | A | IMPLEMENTED | effort-budget gauge | Overview / PM Attention | BLOCKED auth continuity |
| QA | Remaining and failed tests | A | IMPLEMENTED | scoped dashboard result counts | Overview / QA Readiness | BLOCKED auth continuity |
| QA | Blocking defects | A | IMPLEMENTED | scoped open P0/P1 defects | Overview / QA Readiness | BLOCKED auth continuity |
| QA | Evidence completeness | A | IMPLEMENTED | scoped dashboard evidence ratios | Overview / QA Readiness | BLOCKED auth continuity |
| QA | Evidence/sign-off classification | A | PARTIAL | TEST evidence authoritative; INTERNAL/CUSTOMER absent | Overview / QA Readiness | BLOCKED auth continuity |
| Infra | Architecture revision | A | IMPLEMENTED when bound | bound design | Overview / Infra Readiness | BLOCKED route/auth |
| Infra | Feasibility exceptions | A | IMPLEMENTED when bound | bound design feasibility | Overview / Infra Readiness | BLOCKED route/auth |
| Infra | Environment readiness | A | PARTIAL | owner environments lack readiness | Overview / Infra Readiness | BLOCKED route/auth |
| Infra | Connectivity exceptions | A | IMPLEMENTED when bound | bound design edges | Overview / Infra Readiness | BLOCKED route/auth |
| Infra | Implementation readiness | A | PARTIAL | no explicit plan binding | Overview / Infra Readiness | BLOCKED route/auth |
| Infra | Preflight/scoped production readiness | A | PARTIAL | no execution-package binding; scoped row only | Overview / Infra Readiness | BLOCKED route/auth |
| Cross-service | Project Attention | opportunity | IMPLEMENTED | `project_truth/v1` | Project Overview | internal drill-down |
| Cross-service | Go-live readiness | opportunity | DEFERRED | insufficient deterministic governance truth | none | NOT_APPLICABLE |

Acceptance matrix:

```text
PM_NEXT_MILESTONE=PASS
PM_SLIPPAGE=PASS
PM_BLOCKED_DEPENDENCIES=PASS
PM_EFFORT_VARIANCE=PASS

QA_REMAINING=PASS
QA_FAILED=PASS
QA_BLOCKING_DEFECTS=PASS
QA_EVIDENCE_COMPLETENESS=PASS
QA_EVIDENCE_CLASSIFICATION=PARTIAL

INFRA_ARCH_REVISION=PASS
INFRA_FEASIBILITY=PASS
INFRA_ENV_READINESS=PARTIAL
INFRA_CONNECTIVITY=PASS
INFRA_IMPLEMENTATION_READINESS=PARTIAL
INFRA_PREFLIGHT=PARTIAL

PROJECT_ATTENTION=PASS
DELIVERY_HEALTH=PASS
GO_LIVE_READINESS=DEFERRED

OWNER_DEEP_LINK_PM=BLOCKED
OWNER_DEEP_LINK_QA=BLOCKED
OWNER_DEEP_LINK_INFRA=BLOCKED

QA_EMPTY_SEMANTICS=PASS
INFRA_UNBOUND_SEMANTICS=PASS
PARTIAL_FAILURE_BEHAVIOR=PASS

NEW_WRITE_ACTIONS=NOT_APPLICABLE
NEW_DATABASE=NOT_APPLICABLE
AI_FEATURES=NOT_APPLICABLE

UNIT_TESTS=PASS
INTEGRATION_TESTS=PASS
FRONTEND_TESTS=PASS
LINT=PASS
BUILD=PASS
BROWSER_VALIDATION=BLOCKED
PRODUCTION_VALIDATION=PARTIAL

SECURITY_REGRESSION=PASS
GOVERNANCE_REGRESSION=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS
```

The implementation is accepted locally and deployed, but R17.1.3 remains `PARTIAL` until a fresh authorized browser session proves the production representative-project truth and Overview. This status does not weaken the already accepted R17.1.2 baseline.
