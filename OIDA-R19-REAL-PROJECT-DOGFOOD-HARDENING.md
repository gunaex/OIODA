# OIDA R19 — Real Project Dogfood & Product Hardening

## 1. Baseline

Baseline `17cdd6edc8d7c8ea1c485daf1c5f516bccff5ca1` is accepted R18.3. R19 used DOGFOOD → OBSERVE → CLASSIFY → FIX P0/P1 → TEST → DEPLOY → RE-DOGFOOD → STOP. No speculative capability, owner action, database object, scheduler, notification, or customer evidence was added.

## 2. Dogfood Project / Environment

The representative production project is `True Cloud Migration` (`TCM`, `prj_853bcc5700a54c8db170`), tenant `oida`, lifecycle `ACTIVE`. It is not a fabricated R19 project. Production inventory records 12 requirements, 3 baselines, 5 execution handoffs, 4 QA handoffs, 7 change requests, 3 generated human deliverables, 2 TEST signoffs, and existing trace/design/process evidence.

The project has one explicit PM binding, five explicit QA scopes, and explicit Infra `UNBOUND`. Current production has no R17 impact confirmations, routed actions, or resolution rows, so safe read flows were dogfooded on the real project and mutation closure was exercised in an isolated deterministic integration database. No production owner noise was manufactured.

## 3. End-to-End Flow

| Step | Result | Evidence |
| --- | --- | --- |
| Project | PROVEN | active production TCM identity and tenant |
| Truth | PARTIAL | real bound topology; current unauthenticated owner calls fail honestly |
| Attention | PROVEN | degraded sources remain unverified, not false-green |
| Document | PROVEN | three real versions; HD-MIG-01 baselined v1.0 |
| Change | PROVEN | production change records plus deterministic controlled change |
| Impact | PROVEN | one-hop typed projection and stale-document scenario |
| Confirmation | PROVEN | actor, reason, origin, evidence hash, audit and idempotency |
| Action | PARTIAL | full isolated owner-adapter flow; production safe target unavailable |
| Owner Result | PARTIAL | fake deterministic adapter only; no production mutation |
| Resolution | PROVEN | successful action remains `WAITING_ON_OWNER` until QA truth completes |
| Briefing | PROVEN | waiting appears and does not appear as resolved |
| Portfolio | PROVEN | one authorized active production project; scale remains fixture-tested |

The required deterministic integration test covers Change → Impact → Confirmation → Action Preview → explicit Human Execute → Owner Result → Truth Refresh → Resolution Evaluation → Daily Briefing.

## 4. Onboarding / Bindings

Project identity and tenant are explicit. Stored binding truth reports PM `BOUND`, five QA scopes `BOUND`, and Infra `UNBOUND`; no display-name matching or derived production binding is used. Prior authenticated production evidence confirms Account membership and owner access. Current R19 execution has no fresh human browser session, so authenticated onboarding replay is `NOT_TESTABLE_ENVIRONMENT`. Binding truth itself is `SMOOTH`; no P0/P1 binding defect was reproduced.

## 5. Project Truth / Command Center

A new read-only in-machine sample composed the real project without an identity token: PM `UNAUTHORIZED`, QA `UNAUTHORIZED`, Infra `UNBOUND`, 19 attempted downstream calls, 810.54 ms. These stayed distinct and yielded three unverified items—not zeros, readiness, or false blockers. Command Center composition over that snapshot took 135.64 ms and exposed `project_command_center/v1` plus `resolution_intelligence/v1`. Classification: `USABLE_WITH_FRICTION` only because authenticated owner truth was unavailable in this run; no product truth defect.

Prior accepted authenticated evidence remains PM `OK`, QA `OK`, Infra `UNBOUND`, with values cross-checked against owner APIs. R19 did not claim that historical authenticated snapshot was a new live sample.

## 6. Daily Briefing

Read-only first-view generation took 1.88 ms, returned `FIRST_VIEW_CURRENT_BRIEF`, four deterministic focus items, and no fabricated checkpoint. R19 did not mutate a production checkpoint without a human session. Existing race-safe checkpoint tests plus the new closed-loop test prove waiting is retained and successful action is not reported resolved. Classification: `USABLE_WITH_FRICTION`; authenticated Mark Reviewed/re-review is an operational gap.

## 7. Documents / Precheck

Production contains HD-03 v0.1 DRAFT/READY, HD-MIG-01 v1.0 BASELINED/READY, and HD-01 v0.1 DRAFT/READY_WITH_GAPS. A read-only HD-MIG-01 precheck over the current degraded snapshot took 11.88 ms and returned `READY_WITH_GAPS`, preserving unavailable owner truth as gaps rather than fabricating completeness. Earlier authenticated production evidence returned truthful `NOT_READY` for the same document when PM schedule was empty, QA was not started, and Infra was unbound.

No new production draft was generated because no authenticated human requested it. Generation With Gaps is therefore `NOT_TESTABLE_ENVIRONMENT`, not forced green.

## 8. Reviewer Experience

The real HD-MIG-01 reviewer packet took 28.49 ms and returned `reviewer_evidence/v1`, seven cited items, explicit `NOT_RECORDED → 1.0` comparison, deterministic brief, role, exclusions, TEST acceptance evidence, and no AI dependency.

Dogfood found `DOGFOOD-R19-01`: purpose `REVIEW` was paired with gate-policy wording “This approval confirms…” and “explicit acceptance”. This was a P1 authority-language defect. The deterministic packet now supplies review-specific why/instruction/authority text, and the UI labels `Review scope` rather than `Confirm` for reviewer briefs. Sign-off policy itself remains unchanged.

## 9. Change / Impact

Production already contains legitimate change requests and one requirement change; R19 did not create a destructive production change. The deterministic document cross-flow changed a requirement revision, produced `POTENTIALLY_STALE`, surfaced it in reviewer evidence, preserved EXPLICIT/DETERMINISTIC/UNKNOWN boundaries, and left the previous baseline hash immutable. No automatic regeneration occurred.

## 10. Confirmation

The controlled scenario records a human `CONFIRMED` decision against an UNKNOWN QA placeholder, preserving origin provenance, actor, reason, change ID, evidence hash, idempotency, and `customer_acceptance=false`. Existing focused coverage also verifies REJECTED reason requirements, UNRESOLVED/reopen history, rejection memory, conflicts, and stale evidence protection.

## 11. Controlled Action

The controlled flow uses only `ROUTE_QA_VALIDATION_HANDOFF`: preview first, explicit human trigger, current evidence precondition, QA scope binding, idempotent owner call, read-after-write truth refresh, audit, and zero direct owner DB writes.

Dogfood found `DOGFOOD-R19-02`: the backend returns post-action state as `impact_resolution`, while Deliverables read `actionResult.resolution`; immediate resolution status was hidden. The UI now consumes the published backend field and has a frontend contract test. Production owner execution is `NOT_TESTABLE_ENVIRONMENT` because no safe authenticated target was available.

## 12. Resolution

The cross-flow proves `ACTION_SUCCEEDED != RESOLVED`: the action succeeds, incomplete QA evidence evaluates to `WAITING_ON_OWNER`, Resolution Intelligence classifies it as waiting/missing evidence, and Daily Briefing includes it under waiting with no resolved item. Existing tests prove authoritative complete QA truth resolves, later incomplete truth reopens, stale evidence requires recheck, and unavailable truth never becomes green.

## 13. Portfolio

Production has one eligible active project; deleted clone data is excluded. Read-only composition took 720.17 ms, produced one summary, no project failures, first-view portfolio mode, and no cross-project leakage. Multi-project checkpoint, scale 1/5/20/50, and access-removal behavior remain deterministic fixture evidence. Classification: `SMOOTH` for current one-project scope; authenticated portfolio checkpoint is an operational gap.

## 14. AI Experiences

Production reviewer provider status is not configured. `AI_PROVIDER=OPERATIONAL_GAP`; this does not block deterministic reviewer, briefing, command-center, portfolio, or resolution guidance. Regression coverage verifies citations and that AI cannot execute, approve, acknowledge, accept, sign, waive, or resolve.

## 15. Friction Register

| ID | Flow | Finding | Severity | Evidence | Fix | Final Status |
| -- | ---- | ------- | -------- | -------- | --- | ------------ |
| DOGFOOD-R19-01 | Reviewer | REVIEW packet used approval/acceptance wording | P1 | real HD-MIG-01 production packet | purpose-specific deterministic instruction and UI scope label | FIXED / TESTED |
| DOGFOOD-R19-02 | Action → Resolution | UI read `resolution`, API publishes `impact_resolution` | P1 | required closed-loop integration contract and source UI | align UI field; frontend contract test | FIXED / TESTED |
| DOGFOOD-R19-03 | Authentication | no fresh production human session for browser replay | P2 operational | gateway routes return fail-closed 401 | no product change | OPEN / OPERATIONAL |
| DOGFOOD-R19-04 | AI | production provider not configured | P2 operational | runtime provider status null | deterministic fallback retained | OPEN / OPERATIONAL |
| DOGFOOD-R19-05 | Owner action | no safe authenticated mutation target | P2 operational | zero production impact/action/resolution rows | isolated owner-adapter proof; no noise | OPEN / OPERATIONAL |
| DOGFOOD-R19-06 | Portfolio | only one active eligible project | P3 operational | production project inventory | retain scale fixtures; no fake project | OPEN / OPERATIONAL |
| DOGFOOD-R19-07 | History | real HD-MIG-01 has one recorded document version | P3 | reviewer comparison `NOT_RECORDED → 1.0` | disclose limitation; no fake revision | OPEN / HONEST |

## 16. P0/P1 Fixes

P0 found/fixed/remaining: 0/0/0. P1 found/fixed/remaining: 2/2/0. Every product source change maps to DOGFOOD-R19-01 or DOGFOOD-R19-02. No P2/P3 product polishing was performed.

## 17. Performance

| Flow | Measurement | Context |
| --- | ---: | --- |
| Project Truth | 810.54 ms | production in-machine, degraded auth, 19 calls |
| Command Center | 135.64 ms | projection over same truth snapshot |
| Daily Briefing | 1.88 ms | embedded read-only first view |
| Document Precheck | 11.88 ms | projection over existing snapshot |
| Reviewer Brief + Impact | 28.49 ms | real HD-MIG-01 |
| Portfolio | 720.17 ms | one active production project, fresh truth attempt |
| Action / Resolution | response-measured | isolated deterministic integration; no production latency claim |

No SLA is inferred. No measured projection showed clear P1 user latency. Anonymous gateway samples were 141–376 ms and correctly returned HTTP 401.

## 18. Security / Governance / Acceptance Integrity

Tenant-scoped guard tests deny cross-tenant projects; Portfolio includes only its authorized input scope; checkpoints remain user/project scoped; impact confirmation and action require matching project/evidence; resolution evidence is project-scoped. Owner writes pass only through the two allowlisted owner adapters after human preview/execute. Audit records preserve actor, origin, evidence, and `customer_acceptance=false`.

The real project has two `TEST / ACCEPTANCE / ACCEPTED_WITH_EXCEPTIONS` records. Command Center correctly reports `customer_accepted=false`; TEST is not CUSTOMER or FORMAL_EXTERNAL. The cross-flow combines TEST evidence, successful action, and resolution truth and still cannot produce customer acceptance.

Signed/baselined version hashes remain immutable. Flexible governance, Proceed With Risk, Waiver/Exception, Not Applicable, and version-scoped evidence are unchanged. Anonymous Command Center, Briefing, Reviewer Evidence, and Portfolio calls fail closed with HTTP 401.

## 19. Operational Backlog

- AUTH: obtain a fresh normal human session for authenticated browser Command Center, Mark Reviewed, reviewer, and portfolio replay.
- AI PROVIDER: configure and dogfood one production provider; deterministic operation remains complete without it.
- DOGFOOD: perform human multi-device checkpoint replay when authenticated.
- SSO/DEEP LINK: revalidate owner deep links during the authenticated browser pass.
- OWNER SAFE TEST TARGET: provision an explicitly disposable PM/QA target for production preview/execute/reconciliation evidence.
- DOGFOOD: repeat Portfolio dogfood when a second genuinely authorized active project exists.

## 20. Final Product Readiness

The real project is understandable and truth-preserving under both sparse and degraded states. The deterministic closed loop works. The two user-blocking contract/language defects are fixed. No P0 or P1 remains, authority and acceptance boundaries hold, and remaining gaps are isolated operational validation work.

```text
OIDA R19 — REAL PROJECT DOGFOOD & HARDENING FINAL REPORT

BASELINE_HEAD=17cdd6edc8d7c8ea1c485daf1c5f516bccff5ca1
IMPLEMENTATION_COMMIT=PENDING
FINAL_HEAD=PENDING

SOURCE_CODE_CHANGED=YES_TWO_EVIDENCE_BACKED_P1_FIXES
WORKTREE_FINAL=PENDING
CI=PENDING

DOGFOOD_PROJECT=prj_853bcc5700a54c8db170_TRUE_CLOUD_MIGRATION
DOGFOOD_MODE=REAL_PRODUCTION_READS_PLUS_ISOLATED_CONTROLLED_MUTATION_LOOP

ONBOARDING=USABLE_WITH_FRICTION_AUTH_OPERATIONAL_GAP
PROJECT_BINDINGS=PROVEN_PM_BOUND_QA_5_BOUND_INFRA_UNBOUND
PROJECT_TRUTH=PARTIAL_CURRENT_AUTH_DEGRADED_HONEST
COMMAND_CENTER=PROVEN
DAILY_BRIEFING=PROVEN_READ_ONLY_CHECKPOINT_OPERATIONAL_GAP

DOCUMENT_PRECHECK=PROVEN
DOCUMENT_GENERATION=NOT_TESTABLE_ENVIRONMENT
DOCUMENT_VERSIONING=PROVEN_IMMUTABLE_FIXTURE_AND_REAL_BASELINE
REVIEWER_BRIEF=PROVEN_P1_FIXED
AI_REVIEWER=OPERATIONAL_GAP

CHANGE_DETECTION=PROVEN
IMPACT_INTELLIGENCE=PROVEN
HUMAN_CONFIRMATION=PROVEN_CONTROLLED
CONTROLLED_ACTION=PROVEN_CONTROLLED_PRODUCTION_OPERATIONAL_GAP
OWNER_RECONCILIATION=PROVEN_CONTROLLED
RESOLUTION=PROVEN_WAITING_NOT_FALSE_RESOLVED
RESOLUTION_INTELLIGENCE=PROVEN

PORTFOLIO=PROVEN_SINGLE_REAL_PROJECT
PROJECT_COPILOT=DETERMINISTIC_AI_OPERATIONAL_GAP
PORTFOLIO_COPILOT=DETERMINISTIC_AI_OPERATIONAL_GAP

END_TO_END_LOOP=PROVEN_DETERMINISTIC_PARTIAL_PRODUCTION

FRICTION_COUNTS:
P0=0
P1=2
P2=3
P3=2

P0_FIXED=0
P1_FIXED=2
P0_REMAINING=0
P1_REMAINING=0

PERFORMANCE:
COMMAND_CENTER=135.64_MS_PROJECTION
BRIEFING=1.88_MS
PRECHECK=11.88_MS
REVIEWER_BRIEF=28.49_MS_INCLUDING_IMPACT
IMPACT=INCLUDED_IN_REVIEWER_PACKET
ACTION=RESPONSE_MEASURED_CONTROLLED_ONLY
RESOLUTION=RESPONSE_MEASURED_CONTROLLED_ONLY
PORTFOLIO=720.17_MS_ONE_PROJECT

SECURITY=PASS
AUTHORIZATION=PASS_FAIL_CLOSED
CROSS_PROJECT_ISOLATION=PASS
OWNER_WRITE_INTEGRITY=PASS
AUDIT_PROVENANCE=PASS

TEST_VS_INTERNAL_VS_CUSTOMER=PASS
SIGNED_VERSION_IMMUTABILITY=PASS
GOVERNANCE_REGRESSION=PASS
AI_AUTHORITY_BOUNDARY=PASS

DOCUMENT_TESTS=PENDING_FINAL
CROSS_FLOW_TESTS=3_PASS
SECURITY_TESTS=PASS
FOCUSED_REGRESSION_TESTS=60_PASS
FRONTEND_TESTS=12_PASS
GATEWAY_TESTS=PENDING_FINAL
LINT=PASS_WITH_EXISTING_WARNINGS
BUILD=PASS_WITH_EXISTING_BUNDLE_WARNING

DEPLOYMENT=PENDING
PRODUCTION_REVISION_PROOF=PENDING

PRODUCT_READINESS=READY_WITH_ISOLATED_OPERATIONAL_GAPS
R19=ACCEPTED_WITH_OPERATIONAL_GAPS

NEXT_STEP=STOP
```
