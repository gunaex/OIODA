# OIDA R17.1.2 — Cross-Service Project Truth & Live Precheck

## 1. Baseline

- Accepted lineage: R17, R17.1, R17.1.1.
- Accepted handover commit: `3e7aa05fcbe0ddb576354f4cec9dbc20479ebc2d`.
- R17.1.2 baseline HEAD: `a08438ae2b49a75924136820b3979f5f265e2d7e` (`main`).
- This implementation builds on the uncommitted audit/recovery changes listed in `OIDA-INTEGRATION-AUDIT.md`; unrelated external-repository changes were not touched.

## 2. Architecture

`Document Again project bindings → project_truth/v1 → PM/QA/Infra owner APIs in three parallel source groups → Project Overview + Human Deliverable Precheck/Generation`.

The layer lives at Document Again's existing correlation boundary because Document owns the OIDA project ID and precheck. It is a synchronous, ephemeral read model. It persists no PM, QA, or Infra facts. Generation records only the observed contract metadata, sources, provenance and warnings in version-specific readiness evidence.

## 3. Project binding model

`project_bindings/v1` contains `document_project_id`, one PM pointer, zero-or-more QA scope pointers, and one Infra design pointer. Each pointer carries service, external project ID, binding status, optional scope, bound timestamp/source, and observational validation status.

Legacy `pm_project_slug`, `qa_project_slugs`, and `infra_design_id` pointers are migrated in memory with `source=LEGACY_POINTER`. Writes preserve compatibility while maintaining v1. The UI now requires an explicit user selection. Name matching and derived `wp-*` QA slugs were removed.

Binding/runtime states: `BOUND`, `UNBOUND`, `INVALID`, `UNAVAILABLE`, `UNAUTHORIZED`, `FORBIDDEN`, `UNKNOWN`. Runtime validation never silently rewrites a stored binding.

## 4. Truth contract

`project_truth/v1` returns project ID, generated time, bindings, three source metadata blocks, domain-preserving PM/QA/Infra truth, overall freshness, partial flag, warnings, duration, and downstream call count.

Each source includes service, external ID, status, source revision/version, source update time, retrieval time, age, freshness, safe error category/message and duration. Normalized domain truth retains entity/revision/retrieval provenance.

## 5–7. Truth mappings

| Truth | Authority | Actual source API | Normalized field | Consumer | Provenance | Status |
|---|---|---|---|---|---|---|
| Project/schedule | PM Again | `GET /api/{slug}/dashboard`, `/gantt` | `project_status`, `schedule_status`, item counts | Overview / Precheck | PM slug, source version, retrieved time | PASS |
| Milestones/dependencies | PM Again | `GET /api/{slug}/gantt` | `milestone_status/count`, `dependency_status/count` | Overview / Precheck | PM project provenance | PASS |
| Effort | PM Again | `GET /api/{slug}/effort-estimates/summary` | `effort_status`, `effort` | Overview / future precheck modules | PM project provenance | PASS |
| QA readiness/execution | QA Again | `GET /api/{slug}/dashboard` | `readiness_status`, `execution_status`, counts/pass rate | Overview / Precheck | QA scope IDs, retrieved time | PASS |
| Test definition | QA Again | `GET /api/{slug}/suites` | `test_definition_status`, `suite_count` | Overview / Precheck | QA scope provenance | PASS |
| Defect blocking | QA Again | `GET /api/{slug}/defects` | open/blocking defect counts | Overview / Precheck | QA scope provenance | PASS |
| QA evidence | QA Again | `GET /api/{slug}/dashboard` | `evidence_status/completeness` | Precheck | QA scope provenance | PASS |
| Target architecture | Infra Again | `GET /api/v1/designs/{design_id}` | architecture status/revision/component/connection counts | Overview / Precheck | design ID and revision | PASS |
| Environments | Infra Again | `GET /api/v1/environments` | environment status/count | Overview / Precheck | Infra retrieval provenance | PASS |
| Production readiness | Infra Again | `GET /api/v1/production-readiness` | readiness status | Overview / Precheck | Infra retrieval provenance | PARTIAL — owner response is global until project/workspace linkage exists |

## 8. Provenance model

Material domain groups carry `source_service`, `source_entity_id`, `source_revision`, and `retrieved_at`. Precheck copies this provenance onto every external standard/dependency statement. The UI exposes it via drill-down without cluttering the document list.

## 9. Freshness model

Source timestamps are used only when owners provide them. Thresholds are configurable through `PROJECT_TRUTH_FRESH_SECONDS` (default 300) and `PROJECT_TRUTH_STALE_SECONDS` (default 1800). States are `FRESH`, `AGING`, `STALE`, `UNKNOWN`. A stale owner response changes source status to `STALE`; truth remains inspectable but precheck treats verification as unknown. No last-known cache exists, so cached stale truth cannot be confused with current truth.

## 10. Failure/degraded-state model

`OK`, `EMPTY`, `UNBOUND`, `UNAUTHORIZED`, `FORBIDDEN`, `UNAVAILABLE`, `INVALID`, `ERROR`, and `STALE` are distinct. Connect/timeouts are unavailable; 401/403 stay distinct; 404 validates the pointer as invalid; 5xx is error. Failed truth is `null`, never `{count: 0}` or `[]`. One source failure does not discard successful sources.

Structured diagnostics include project ID, service, binding, result status, duration, error category and downstream call count. Authorization content and evidence bodies are never logged.

## 11. Document Precheck integration

The five R17 readiness categories and flexible governance behavior remain intact. Precheck now receives the live snapshot, enriches owner-controlled standards with source metadata/reason/provenance, counts `UNKNOWN` separately, and adds deterministic migration dependencies for PM schedule, QA readiness, Infra target architecture and connectivity.

Owner outage yields `UNKNOWN` with “could not be verified”; it does not claim missing truth. PM partial schedule + QA blocking defect + Infra ready architecture deterministically yields `READY_WITH_GAPS` with reasons and revision provenance. Generation and immutable-revision creation use the same snapshot and preserve its source evidence in `readiness_at_generation`.

## 12. Project Overview integration

Project Overview calls `GET /api/projects/{id}/truth`. Its delivery cards and expandable cross-service truth panel use this contract. The prior independent PM functions/tasks and QA dashboard summary reads were removed. Each source shows binding, status, freshness, retrieval time, key domain signals and safe error details.

## 13. Tests

- Truth/adapters: 12 passed. Covers v1/legacy/unbound/invalid binding; PM/QA/Infra healthy; empty semantics; 401; 403; 404; 500; timeout; partial source success; stale; provenance; call count; critical combined precheck; failure integrity.
- Full Document Again suite: 132 passed.
- OIDA lint: exit 0 with pre-existing warnings.
- OIDA production build: PASS, 1,783 modules.
- No dedicated browser-component test framework exists; frontend behavior is build/lint validated and backend contract behavior is deterministic-test validated.

## 14. Runtime evidence and performance

Healthy bound snapshot: 9 owner calls. PM/QA/Infra groups execute in parallel; the three calls within each group are sequential. Per-source timeout defaults to 5 seconds and is configurable. Combined latency is approximately the slowest source group, not the sum of all three groups. Every response reports measured per-source and combined duration. No cache or retries are used; authorization errors are attempted once.

Actual live latency could not be measured without a credentialed, bound runtime. Mock-transport test latency is not presented as production evidence.

## 15. Browser validation

`BLOCKED_BY_ENVIRONMENT`: no browser automation capability or credentialed OIDA session was available. Build success is not classified as browser validation.

## 16. Production validation

`BLOCKED`: no real Account Again credentials or authorization to deploy/exercise the production services was available. No deployment was attempted and no customer evidence/signature was created.

## 17. Remaining gaps

- Infra production-readiness endpoint is global; a formal Document-project ↔ Infra-workspace pointer should scope it.
- QA multiple scopes are aggregated; per-scope summaries can be added without changing v1.
- Source calls are sequential within each service group; batching/owner summary endpoints could reduce nine calls.
- Frontend component tests and credentialed browser/error-state validation remain outstanding.
- Existing PM/QA feature pages still contain some audit-identified empty-on-error handling outside the new shared Overview/Precheck path.

## 18. Acceptance matrix and recommendation

| Item | Result | Evidence / non-PASS reason |
|---|---|---|
| PROJECT_BINDING_CONTRACT | PASS | `project_bindings/v1`; explicit UI selection; legacy in-memory migration |
| PROJECT_TRUTH_CONTRACT | PASS | `project_truth/v1` shared endpoint/service |
| CONTRACT_VERSIONING | PASS | explicit contract identifiers |
| PM_TRUTH_ADAPTER | PASS | dashboard/Gantt/effort owner APIs |
| QA_TRUTH_ADAPTER | PASS | dashboard/suites/defects owner APIs |
| INFRA_TRUTH_ADAPTER | PASS | design/environments/readiness owner APIs |
| PROVENANCE | PASS | contract, precheck and UI drill-down |
| FRESHNESS | PASS | configurable FRESH/AGING/STALE/UNKNOWN |
| PARTIAL_FAILURE_HANDLING | PASS | independent source results and test |
| AUTH_ERROR_HANDLING | PASS | 401/403 distinct and tested |
| STALE_DATA_HANDLING | PASS | stale marked and tested; no cache |
| PROJECT_OVERVIEW_TRUTH | PASS | shared truth endpoint is sole bounded summary source |
| DOCUMENT_PRECHECK_PM | PASS | schedule/dependency mapping and critical test |
| DOCUMENT_PRECHECK_QA | PASS | readiness/blocking defects and critical test |
| DOCUMENT_PRECHECK_INFRA | PASS | architecture/connectivity with revision provenance |
| CROSS_SERVICE_PRECHECK | PASS | combined truth changes readiness deterministically |
| DUPLICATED_BOUNDED_TRUTH | PASS | no bounded facts persisted/editable in OIDA/Document |
| FAKE_DATA_IN_PRODUCTION | PASS | no mock/fallback path in new production code |
| CUSTOMER_ACCEPTANCE_INTEGRITY | PASS | QA evidence remains QA evidence; sign-off model untouched |
| UNIT_TESTS | PASS | 12 truth tests; full suite 132 passed |
| INTEGRATION_TESTS | PASS | combined owner responses → precheck tested |
| CONTRACT_TESTS | PASS | bindings/status/provenance/degraded contracts tested |
| FRONTEND_TESTS | PARTIAL | no component-test harness; lint/build pass |
| BUILD | PASS | production Vite build |
| LINT | PASS | exit 0; warnings remain |
| BROWSER_VALIDATION | BLOCKED | tooling/credentialed session unavailable |
| PRODUCTION_VALIDATION | BLOCKED | credentials/deployment authority unavailable |

Recommended next step: production/browser hardening first—deploy this focused foundation through the existing release process, validate real bindings/latencies/error states, then decide between capability projection parity and cross-service change-impact intelligence based on observed user workload.

## OIDA R17.1.2 — Final report

```text
BASELINE_HEAD=a08438ae2b49a75924136820b3979f5f265e2d7e
FINAL_HEAD=a08438ae2b49a75924136820b3979f5f265e2d7e (working tree; not committed)
PROJECT_BINDING_CONTRACT=PASS
PROJECT_TRUTH_CONTRACT=PASS
TRUTH_CONTRACT_VERSION=project_truth/v1
PM_TRUTH=PASS
QA_TRUTH=PASS
INFRA_TRUTH=PASS
PM_FIELDS_MAPPED=status,schedule,milestones,progress,effort,dependencies
QA_FIELDS_MAPPED=readiness,test-definition,execution,results,defects,evidence
INFRA_FIELDS_MAPPED=architecture,revision,components,connections,environments,readiness
PROVENANCE=PASS
FRESHNESS=PASS
PARTIAL_SOURCE_FAILURE=PASS
STALE_DATA_BEHAVIOR=PASS
PROJECT_OVERVIEW=PASS
DOCUMENT_PRECHECK_PM=PASS
DOCUMENT_PRECHECK_QA=PASS
DOCUMENT_PRECHECK_INFRA=PASS
CROSS_SERVICE_PRECHECK=PASS
DUPLICATED_BOUNDED_TRUTH=PASS
FAKE_DATA_IN_PRODUCTION=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS
UNIT_TESTS=PASS
INTEGRATION_TESTS=PASS
CONTRACT_TESTS=PASS
BUILD=PASS
LINT=PASS
BROWSER_VALIDATION=BLOCKED_BY_ENVIRONMENT
PRODUCTION_VALIDATION=BLOCKED
PERFORMANCE:
PM_LATENCY=measured per response; live evidence blocked
QA_LATENCY=measured per response; live evidence blocked
INFRA_LATENCY=measured per response; live evidence blocked
COMBINED_LATENCY=measured per response; live evidence blocked
DOWNSTREAM_CALL_COUNT=9 healthy; 0 for fully unbound
R17_1_2=ACCEPTED (all 15 implementation criteria met; browser/production validation remains explicitly environment-blocked)
```
