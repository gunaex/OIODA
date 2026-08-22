# OIDA R17.5 — Controlled Cross-Service Action Routing

## 1. Baseline

R17.4 is accepted at `861b845a4f949cb11500b0fb6fea4a67cd052b10`. R17.5 preserves `impact_confirmation/v1` and requires a current `CONFIRMED` relationship before routing. OIDA remains initiator/orchestrator; owner services persist PM/QA truth.

## 2. Decision-Lite Owner Write Inventory

| Service | Write Action | API Exists | Risk | Selected R17.5? | Reason |
| ------- | ------------ | ---------- | ---- | --------------- | ------ |
| PM Again | Canonical DeliveryWorkPackage intake | Yes, service-authenticated and idempotent | LOW | Yes | Existing Document→Conductor→PM authority path and read status |
| QA Again | Canonical QARequest intake | Yes, service-authenticated and idempotent | LOW | Yes | Existing Document→Conductor→QA authority path and result reference |
| PM Again | Direct task/status edit or issue | Yes, human app API | MEDIUM | No | Delegated-human/service route and stable target preconditions not proven |
| QA Again | Direct defect creation | Yes, human app API | MEDIUM | No | Scope/permission delegation and owner idempotency not proven for OIDA |
| Document Again | Human deliverable revision | Yes | MEDIUM | No | Existing explicit generation workflow remains safer; no auto-content rewrite |
| Infra Again | design/apply/deploy/promotion/rollback | APIs exist | HIGH/PROHIBITED | No | Explicit Wave 1 non-scope |

Document Again cannot impersonate Conductor: PM/QA intake accepts Conductor’s service identity. The selected path uses the existing Conductor relay, preserving least privilege.

## 3. Selected Wave 1 Actions

1. `ROUTE_PM_DELIVERY_HANDOFF`: create a versioned local execution handoff, explicitly dispatch through Conductor, PM Again persists an idempotent external work-package reference, then OIDA reads the acknowledged handoff and refreshes project truth.
2. `ROUTE_QA_VALIDATION_HANDOFF`: create a versioned QA-validation handoff, explicitly dispatch through Conductor, QA Again persists an idempotent external request, then OIDA reconciles the acknowledgement and refreshes project truth.

Both are low risk, human executed, bounded, and carry stable handoff/idempotency identities. They record follow-up; they do not resolve the impact.

## 4. Action Routing Contract

`action_route/v1` includes route/project/impact/confirmation identity, allowlisted action type, target service/entity, actor/time, typed parameters, exact precondition snapshot/evidence hash, idempotency key, precise status, safe result reference, failure category, and immutable event history. Supported states include `READY`, `REQUIRES_INPUT`, `NOT_AVAILABLE`, `EXECUTING`, `SUCCEEDED`, `STALE`, `CONFLICT`, `UNAUTHORIZED`, `FORBIDDEN`, `OWNER_UNAVAILABLE`, `VALIDATION_FAILED`, `NOT_SUPPORTED`, `UNKNOWN_RESULT`, and `OWNER_ERROR`.

## 5. Action Registry

`impact_action_registry/v1` contains only the two selected `CONTROLLED_OWNER_WRITE` actions. Each declares owner, LOW risk, required inputs/permission, and idempotency behavior. Arbitrary action names are rejected. Customer acceptance, sign-off, waiver approval, Infra deployment/rollback, deletion, automatic test execution, bulk PM update, regeneration, and CR creation are prohibited.

## 6. Preconditions

Preview and execution verify: allowlisted type, guarded project, current confirmed relationship, exact evidence hash, current binding, and required parameters. PM requires a bound PM project. QA requires a bound scope; multiple scopes return `REQUIRES_INPUT` until the human selects an exact scope. Stale/rejected/unresolved confirmation blocks with zero owner calls.

## 7. Authorization

All endpoints use existing Account Again actor resolution, tenant/project guarding, and gateway deny-by-default authentication. Owner writes use the Document service identity only to call Conductor; Conductor alone holds the accepted downstream identity. No credential reaches the frontend, no global admin role/token was added, and anonymous execution returns 401.

## 8. Idempotency / Concurrency

The route key covers project, confirmation, action, inspected parameters, and evidence hash and is unique in `impact_action_routes`. Repeated execution returns the same route and makes one owner-adapter call. Conductor uses the stable handoff ID and PM/QA use native idempotency keys. Immutable `impact_action_events` retain lifecycle history. No automatic retry occurs.

## 9. Owner Mutation Paths

```text
Human Execute → Document action route → versioned handoff
→ authenticated Conductor document-handoff relay
→ PM DeliveryWorkPackage / QA QARequest owner API
→ owner persistence → external owner reference
```

There is no direct PM/QA/Infra database import or write, no frontend owner mutation, and no shadow owner object in OIDA. Local rows are orchestration evidence only.

## 10. Reconciliation

Success requires the owner response plus read-after-write of the local acknowledged handoff with a non-empty external reference. A transport timeout becomes `UNKNOWN_RESULT`, performs one local acknowledgement reconciliation, and requires reconciliation before a manual retry. Owner errors never become success. After success, `project_truth/v1` is rebuilt and its relevant source status is recorded. Impact is not auto-resolved.

## 11. Audit

`ACTION_REQUESTED`, `ACTION_EXECUTION_STARTED`, `ACTION_SUCCEEDED`, `ACTION_FAILED`, and `ACTION_RECONCILED` are immutable action events. Existing audit evidence records actor, action/target, confirmation/evidence context, owner result or failure category, `human_executed=true`, and `customer_acceptance=false`. No secret or full evidence packet is sent downstream.

## 12. UX

A current human-confirmed PM/QA context exposes `Review PM Handoff` or `Review QA Handoff`. The deterministic preview shows target, exact mutation, non-effects, evidence, required inputs, risk/mode, Cancel, and a separate `Execute Human-Approved Action`. Buttons disable during execution. Success identifies the owner reference; failure preserves category/detail; both state that impact remains unresolved.

## 13. AI Boundary

AI can explain or recommend only allowlisted action types. Preview performs no write. Execution exists only behind the explicit human handler and records `human_triggered=true`, `autonomous=false`. Unknown/model-invented tools are `NOT_SUPPORTED`; prohibited types never execute. `AI_AUTO_EXECUTION=0`.

## 14. Tests

Document Again: **176 passed**. Focused routing/impact/reviewer: **40 passed**. Frontend: **11 passed**. Gateway: **3 passed**. Tests cover preview/no write, allowlist/prohibited types, confirmed/stale/rejected preconditions, PM success, one-call double execution, immutable lifecycle/audit, truth refresh, QA multi-scope input, timeout unknown result, owner unavailable, no fake success/retry, no customer acceptance, and zero direct owner DB writes. Existing Conductor/PM/QA contract suites cover relay/native intake idempotency and owner persistence.

Lint passed with pre-existing warnings. Build passed with the existing bundle-size warning.

## 15. Performance

The deterministic preview is local. The routing test adapter reports owner mutation **2.0 ms** and reconciliation **1.0 ms**; production latency remains exposed per route as preview, owner mutation, reconciliation, truth refresh, and total timing. Network production mutation was intentionally not performed without a safe authenticated target. Correctness/idempotency remain the priority.

## 16. Deployment

Implementation `a50284410b8f9a5625d179220c132350d497d6f0` passed CI run `32565701208`. Document Again deployed as Fly release **25**, image `deployment-01M0MDMZM9BCKRHHYHQWP7232M`, with one passing check and HTTP 200 health. Runtime inspection confirmed `impact_action_routes` and `impact_action_events` exist.

OIDA Web production deployment is Cloudflare Pages `edae3d11`, sourced from the verified implementation SHA, serving `index-BXd-rs8P.js` and `index-tnt_lJ5y.css`. Anonymous execution is HTTP 401. Owner/Conductor/Gateway components were unchanged and not redeployed.

## 17. Operational Backlog

- Carry forward `OPS-AI-01`, `OPS-AI-02`, `OPS-AUTH-01`, `OPS-AI-03`, `OPS-IMPACT-01`, and `OPS-AUTH-IMPACT-01`.
- `OPS-ACTION-01`: authenticated safe PM/QA mutation dogfood in a non-customer target with valid bindings and explicit cleanup policy.

## 18. Deferred High-Risk Actions

Direct PM task/issue mutation, direct QA defect creation, automatic QA rerun, document auto-regeneration, bulk mutation, all Infra apply/deploy/provision/promotion/rollback, CR/waiver creation, customer acceptance/sign-off, go-live approval, and autonomous remediation remain deferred.

## 19. Acceptance

| Action | Human Trigger | Owner API | Owner Result | Reconciled | Audit | Truth Refreshed |
| ------ | ------------- | --------- | ------------ | ---------- | ----- | --------------- |
| PM delivery handoff | Explicit Execute | Conductor relay → PM DeliveryWorkPackage | external work reference | Yes | Yes | Yes |
| QA validation handoff | Explicit Execute | Conductor relay → QA QARequest | external QA request | Yes | Yes | Yes |

```text
ACTION_ROUTE_CONTRACT=PASS
ACTION_REGISTRY=PASS
ACTION_PREVIEW=PASS
PRECONDITION_CHECK=PASS
HUMAN_TRIGGER_REQUIRED=PASS
AI_AUTO_EXECUTION_PROTECTION=PASS
OWNER_API_ONLY=PASS
DIRECT_OWNER_DB_WRITES=PASS (0)
AUTHORIZATION=PASS
LEAST_PRIVILEGE=PASS
IDEMPOTENCY=PASS
CONCURRENCY=PASS
STALE_ACTION_PROTECTION=PASS
UNKNOWN_RESULT_HANDLING=PASS
RECONCILIATION=PASS
READ_AFTER_WRITE=PASS
TRUTH_REFRESH=PASS
PM_ACTION_ROUTING=PASS
QA_ACTION_ROUTING=PASS
DOCUMENT_ACTION_ROUTING=NOT_APPLICABLE (DEFERRED)
INFRA_ACTION_ROUTING=NOT_APPLICABLE (PROHIBITED WAVE 1)
ACTION_AUDIT=PASS
OWNER_RESULT_REFERENCES=PASS
AI_SUGGESTED_ACTIONS=PASS
UNKNOWN_ACTION_REJECTION=PASS
LOCAL_ORCHESTRATION_WRITES=PASS
CROSS_SERVICE_DOMAIN_WRITES=PASS (PM DWP, QA REQUEST)
AUTONOMOUS_ACTIONS=PASS (0)
SECURITY_REGRESSION=PASS
GOVERNANCE_REGRESSION=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS
DOCUMENT_TESTS=PASS (176)
ACTION_ROUTING_TESTS=PASS
IDEMPOTENCY_TESTS=PASS
AUTHORIZATION_TESTS=PASS
OWNER_CONTRACT_TESTS=PASS
AI_SAFETY_TESTS=PASS
FRONTEND_TESTS=PASS (11)
GATEWAY_TESTS=PASS (3)
LINT=PASS
BUILD=PASS
DEPLOYMENT=PASS
PRODUCTION_REVISION_PROOF=PASS
AUTHENTICATED_ACTION_DOGFOOD=BLOCKED
```

`R17.5 = ACCEPTED_WITH_OPERATIONAL_GAPS`. The two controlled owner routes are implemented, tested, deployed, and safe without AI. A live mutation was not manufactured without an authenticated non-customer target.

---

## OIDA R17.5 — CONTROLLED CROSS-SERVICE ACTION ROUTING FINAL REPORT

```text
BASELINE_HEAD=861b845a4f949cb11500b0fb6fea4a67cd052b10
IMPLEMENTATION_COMMIT=a50284410b8f9a5625d179220c132350d497d6f0
FINAL_HEAD=ARTIFACT COMMIT (EXACT SHA REPORTED AT HANDOFF)
SOURCE_CODE_CHANGED=YES
WORKTREE_FINAL=CLEAN AND SYNCHRONIZED AT HANDOFF
CI=PASS (32565701208)
DECISION_LITE_RESULT=USE EXISTING DOCUMENT→CONDUCTOR→OWNER HANDOFF AUTHORITY PATH
OWNER_WRITE_APIS_DISCOVERED=PM DWP, QA REQUEST, DIRECT PM/QA HUMAN APIS, DOCUMENT REVISION, HIGH-RISK INFRA APIS
WAVE1_ACTIONS_SELECTED=2
ACTION_ROUTE_CONTRACT=action_route/v1 PASS
ACTION_REGISTRY=impact_action_registry/v1 PASS
SELECTED_ACTIONS:
1. ROUTE_PM_DELIVERY_HANDOFF
2. ROUTE_QA_VALIDATION_HANDOFF
ACTION_PREVIEW=PASS
PRECONDITION_CHECK=PASS
HUMAN_TRIGGER_REQUIRED=PASS
OWNER_API_ONLY=PASS
DIRECT_OWNER_DB_WRITES=0
AUTHORIZATION=PASS
LEAST_PRIVILEGE=PASS
IDEMPOTENCY=PASS
CONCURRENCY=PASS
STALE_ACTION_PROTECTION=PASS
UNKNOWN_RESULT_HANDLING=PASS
RECONCILIATION=PASS
READ_AFTER_WRITE=PASS
TRUTH_REFRESH=PASS
PM_ACTION_ROUTING=PASS
QA_ACTION_ROUTING=PASS
DOCUMENT_ACTION_ROUTING=DEFERRED
INFRA_ACTION_ROUTING=PROHIBITED
ACTION_AUDIT=PASS
OWNER_RESULT_REFERENCES=PASS
AI_SUGGESTED_ACTIONS=ALLOWLIST ONLY
AI_AUTO_EXECUTION=0
UNKNOWN_ACTION_REJECTION=PASS
LOCAL_ORCHESTRATION_WRITES=ACTION ROUTE/EVENT + EXISTING HANDOFF/OUTBOX/AUDIT
CROSS_SERVICE_DOMAIN_WRITES=2 TYPES (PM DWP, QA REQUEST)
AUTONOMOUS_ACTIONS=0
PERFORMANCE:
ACTION_PREVIEW_LATENCY=LOCAL / RESPONSE-MEASURED
OWNER_MUTATION_LATENCY=2.0 ms TEST ADAPTER; PRODUCTION RESPONSE-MEASURED
RECONCILIATION_LATENCY=1.0 ms TEST ADAPTER; PRODUCTION RESPONSE-MEASURED
TRUTH_REFRESH_LATENCY=RESPONSE-MEASURED
DOCUMENT_TESTS=176 PASS
IMPACT_TESTS=PASS
ACTION_ROUTING_TESTS=PASS
IDEMPOTENCY_TESTS=PASS
AUTHORIZATION_TESTS=PASS
OWNER_CONTRACT_TESTS=PASS
AI_SAFETY_TESTS=PASS
FRONTEND_TESTS=11 PASS
GATEWAY_TESTS=3 PASS
LINT=PASS WITH PRE-EXISTING WARNINGS
BUILD=PASS WITH EXISTING BUNDLE WARNING
DEPLOYMENT=PASS
PRODUCTION_REVISION_PROOF=FLY 25 + PAGES edae3d11 + SOURCE a502844
AUTHENTICATED_ACTION_DOGFOOD=OPERATIONAL_BACKLOG
SECURITY_REGRESSION=PASS
GOVERNANCE_REGRESSION=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS
OPERATIONAL_BACKLOG:
- existing AI/auth/impact items
- OPS-ACTION-01
DEFERRED:
- High-risk Infra actions
- Automatic QA rerun
- Bulk PM mutations
- Autonomous remediation
- Customer acceptance/sign-off actions
R17_5=ACCEPTED_WITH_OPERATIONAL_GAPS
NEXT_STEP=R17.6 CHANGE-TO-RESOLUTION LOOP; DO NOT IMPLEMENT IN R17.5
```
