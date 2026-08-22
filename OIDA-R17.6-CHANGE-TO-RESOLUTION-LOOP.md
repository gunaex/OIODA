# OIDA R17.6 — Change-to-Resolution Loop

## 1. Baseline

Baseline `62b5d9a63243c7b9694dfbedc37dc1ff30156b3e` was the accepted R17.5 controlled-routing release. R17.6 preserves its explicit human execution and owner-authority boundary.

## 2. Decision-Lite Findings

Action success proves only that a follow-up exists. Wave 1 therefore closes the loop with deterministic PM and QA rules, one current projection, and immutable transitions. No new owner action, worker, waiver system, or autonomous remediation was added.

## 3. Resolution Contract

`impact_resolution/v1` records the change, impact candidate, confirmation, latest route, owner result, state/reason, rule/version, compact pre/post truth references, evidence, and evaluation timestamps. `impact_resolution_rules/v1` exposes the typed registry and the complete state vocabulary.

## 4. Resolution State Model

The contract supports `OPEN`, `ACTION_PLANNED`, `ACTION_IN_PROGRESS`, `WAITING_ON_OWNER`, `RECHECK_REQUIRED`, `RESOLVED`, `RESOLVED_WITH_EXCEPTION`, `NO_LONGER_APPLICABLE`, `BLOCKED`, and `UNKNOWN`. Wave 1 emits only states justified by current inputs; `RESOLVED_WITH_EXCEPTION` remains unavailable without an existing explicit governance reference.

## 5. Resolution Rules

| Impact Type | Action | Required Truth | Resolved Condition | Waiting/Blocked Condition | Rule Version |
| ----------- | ------ | -------------- | ------------------ | ------------------------- | ------------ |
| Human-confirmed PM delivery impact | `ROUTE_PM_DELIVERY_HANDOFF` | PM source `OK`; matching owner work package/handoff | matching entity explicitly `COMPLETE`, `COMPLETED`, `RESOLVED`, or `DONE` | successful creation without completion → `WAITING_ON_OWNER`; unavailable owner → `BLOCKED` | `PM-DELIVERY-HANDOFF-COMPLETION` v1 |
| Human-confirmed QA scope impact | `ROUTE_QA_VALIDATION_HANDOFF` | QA source `OK`; authoritative evidence and execution counts | evidence complete/available and remaining, failed, blocked, and blocking-defect counts all zero | successful request without evidence → `WAITING_ON_OWNER`; unavailable owner → `BLOCKED` | `QA-VALIDATION-EVIDENCE-COMPLETE` v1 |

Unknown owner truth produces `UNKNOWN`; uncertain mutation result produces `RECHECK_REQUIRED`; ordinary action failure leaves the impact `OPEN`. No local action status can produce `RESOLVED`.

## 6. Owner Truth Re-evaluation

Successful execution reuses the fresh `project_truth/v1` already fetched by R17.5, so it adds zero downstream calls. Explicit `Recheck` performs a fresh read-only truth refresh through the normal project authorization boundary. Evaluation is limited to the confirmation, latest route, relevant PM or QA domain, and one rule.

## 7. Pre/Post Truth

Pre-action linkage stores the action evidence hash and precondition snapshot hash. Post-action linkage stores contract/version metadata, source status/revision, normalized relevant-domain facts, and a snapshot hash—never an owner database copy.

## 8. Resolution History

`impact_resolution_events` is append-only and transition-hash deduplicated. Unchanged rechecks do not create audit spam. Reopening emits `IMPACT_RESOLUTION_REOPENED`; resolved transitions emit `IMPACT_RESOLVED`. Every audit record declares `customer_acceptance=false` and `ai_authority=false`.

Representative lifecycle:

| timestamp | state | reason | evidence | actor/system |
| --------- | ----- | ------ | -------- | ------------ |
| T0 | `WAITING_ON_OWNER` | QA request exists; completion evidence absent | confirmation, route, QA truth H1 | deterministic evaluator |
| T1 | `RESOLVED` | QA completion rule satisfied | QA truth H2, rule v1 | deterministic evaluator |
| T2 | `WAITING_ON_OWNER` | completion condition returned | QA truth H3 | deterministic evaluator / reopened |

## 9. Project Attention Integration

The project resolution projection counts `new`, `in_progress`, `waiting`, `blocked`, `resolved`, and `unverified`. Resolved IDs are separated as recently resolved and explicitly excluded from current blockers; all records remain in history.

## 10. Reviewer Integration

`reviewer_change_brief/v1` now includes compact deterministic resolution counts, unresolved IDs, and resolved IDs. The main brief remains focused while the impact panel displays current state, owner wait, rule, evidence time, recheck, and timeline.

## 11. AI Boundary

AI resolution authority is `NONE`. AI can explain deterministic evidence but cannot write state. A regression test proves an AI claim of resolution cannot override `WAITING_ON_OWNER`.

## 12. UX / Timeline

The existing impact card now shows resolution state and reason, rule/version, evaluation time, owner responsibility where known, a read-only `Recheck authoritative truth` control, and immutable transition history. It explicitly says action success is not resolution and customer acceptance is separate.

## 13. Tests

Document Again: **180 passed**. Focused resolution/routing/impact/reviewer: **44 passed**. Frontend: **11 passed**. Gateway: **3 passed**. Critical coverage includes action-success-not-resolved, authoritative resolution, unknown truth, stale evidence, reopen, history deduplication, AI non-authority, routing idempotency, and customer-acceptance-negative audit metadata.

## 14. Performance

Unit evaluation is sub-millisecond on fixture truth and returns `evaluation_latency_ms`. Execution downstream calls remain unchanged because the evaluator reuses R17.5 truth. Recheck cost is one existing `project_truth/v1` fan-out; no polling or background infrastructure was added. History is a project-indexed local read.

## 15. Deployment

Implementation `d52e19a6b65af4a090f413129468c565e1a51953` passed CI run `32566314713`. Document Again deployed as Fly release **26**, image `deployment-01M0MEEWWQ62Y1JTBJNFHPHV3M`, with one passing check and HTTP 200 health. Runtime inspection confirmed `impact_resolutions` and `impact_resolution_events` exist.

OIDA Web production deployment is Cloudflare Pages `fb2868b5`, sourced from `d52e19a`, serving `index-DTobTVAq.js` and `index-CRt5ItaM.css`. Anonymous registry and project-history requests both return HTTP 401. Account, PM, QA, Infra, Conductor, and Gateway were unchanged and not redeployed.

## 16. Operational Backlog

- Carry forward `OPS-AI-01`, `OPS-AI-02`, `OPS-AUTH-01`, `OPS-AI-03`, `OPS-IMPACT-01`, `OPS-AUTH-IMPACT-01`, and `OPS-ACTION-01`.
- `OPS-RESOLUTION-01`: authenticated PM/QA resolution dogfood against a safe bound project with owner completion evidence.
- `RESOLVED_WITH_EXCEPTION` remains dormant until an existing governed exception record can be linked without inventing a second waiver system.

## 17. Deferred Autonomous Remediation

Automatic QA rerun, PM mutation, Infra execution, document regeneration, customer acceptance, SLA policy, generic workflows, and all self-healing behavior remain out of scope. New owner action types: **0**.

## 18. Acceptance

| Change | Impact | Confirmation | Action | Owner Result | Post-Truth | Resolution |
| ------ | ------ | ------------ | ------ | ------------ | ---------- | ---------- |
| document change | QA scope impact | human `CONFIRMED` | QA validation handoff | request `ACKNOWLEDGED` | evidence missing | `WAITING_ON_OWNER` |
| same change | same impact | same immutable confirmation | no new mutation; recheck | existing request | evidence complete; zero remaining/failures/blockers | `RESOLVED` |

```text
IMPACT_RESOLUTION_CONTRACT=PASS
RESOLUTION_STATE_MODEL=PASS
RESOLUTION_RULE_REGISTRY=PASS
ACTION_SUCCESS_NOT_AUTO_RESOLVED=PASS
OWNER_TRUTH_REEVALUATION=PASS
PRE_POST_TRUTH_LINKAGE=PASS
RESOLUTION_HISTORY=PASS
REOPEN_BEHAVIOR=PASS
STALE_RESOLUTION_PROTECTION=PASS
PROJECT_ATTENTION_INTEGRATION=PASS
REVIEWER_BRIEF_INTEGRATION=PASS
AI_REVIEWER_INTEGRATION=PASS
AI_RESOLUTION_AUTHORITY=NONE
AUTONOMOUS_REMEDIATION=0
NEW_OWNER_ACTION_TYPES=0
CUSTOMER_ACCEPTANCE_PROTECTION=PASS
GOVERNANCE_EXCEPTION_LINKAGE=DEFERRED_UNTIL_AUTHORITATIVE_RECORD_EXISTS
PERMISSION_BOUNDARY=PASS_EXISTING_PROJECT_AUTH
PARTIAL_SERVICE_BEHAVIOR=PASS_DOMAIN_SCOPED
UNIT_TESTS=180_PASS
RESOLUTION_TESTS=4_PASS
ACTION_INTEGRATION_TESTS=PASS
AUTHORIZATION_TESTS=PASS_EXISTING_ROUTER_BOUNDARY
AI_SAFETY_TESTS=PASS
FRONTEND_TESTS=11_PASS
GATEWAY_TESTS=3_PASS
LINT=PASS_WITH_PRE_EXISTING_WARNINGS
BUILD=PASS_WITH_PRE_EXISTING_BUNDLE_WARNING
DEPLOYMENT=PASS_DOCUMENT_RELEASE_26_AND_WEB_FB2868B5
PRODUCTION_REVISION_PROOF=PASS
AUTHENTICATED_DOGFOOD=OPERATIONAL_GAP_OPS_RESOLUTION_01
SECURITY_REGRESSION=PASS
GOVERNANCE_REGRESSION=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS
R17_6=ACCEPTED_WITH_OPERATIONAL_GAPS
```
