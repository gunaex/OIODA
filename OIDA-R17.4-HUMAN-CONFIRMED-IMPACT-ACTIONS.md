# OIDA R17.4 — Human-Confirmed Impact Actions

## 1. Baseline

R17.3 remains `ACCEPTED_WITH_OPERATIONAL_GAPS` at `84578a08a9b091fa5aff0eb4a11d6e6e6a163845`. Its typed relationship, change, and impact contracts remain authoritative inputs. R17.4 does not reopen or redesign them.

## 2. Decision-Lite Findings

Document Again already owns project/tenant guards, Account Again actor resolution, an immutable audit log, and the reviewer/impact evidence context. The smallest safe write boundary is therefore a local immutable confirmation model in the existing database. PM/QA/Infra mutation APIs and reliable owner deep-link SSO are outside this boundary. Confirmation focuses on `AI_SUGGESTED` and honest unresolved-domain placeholders; `EXPLICIT` and `DETERMINISTIC` relationships remain known without reconfirmation.

## 3. Human Confirmation Model

`impact_confirmation/v1` records `NOT_REVIEWED` implicitly and persists `CONFIRMED`, `REJECTED`, or `UNRESOLVED`. `STALE` is a safe derived read status when the current evidence hash differs. A confirmed advisory/unknown origin has effective context `HUMAN_CONFIRMED`, but its `relationship_class_at_review` and full origin snapshot remain unchanged. `APPROVED` is not used.

Confirm, reject, and leave unresolved are implemented. Reject requires a reason; other reasons are optional. An authorized human can explicitly reopen a confirmed/rejected context by recording `UNRESOLVED`; history is append-only.

## 4. Authority / Provenance

Confirmation means only “relevant in this project context.” It is not owner-service truth, document approval, governance approval, customer acceptance, QA execution, or deployment authorization. Records carry project, relationship/candidate/change IDs, original class and snapshot, exact evidence hash and relationship version, evidence references, actor identity/role/org where supplied, and review timestamp.

| Relationship | Original Class | Human Decision | Effective Context | Evidence Version | Actor/Audit |
| ------------ | -------------- | -------------- | ----------------- | ---------------- | ----------- |
| Unresolved QA context for document version | UNKNOWN | CONFIRMED | HUMAN_CONFIRMED | reviewer packet hash H1 | Account actor / `IMPACT_RELATIONSHIP_CONFIRMED` |
| AI-proposed requirement-to-component link | AI_SUGGESTED | REJECTED | REJECTED | H1 | Account actor / `IMPACT_RELATIONSHIP_REJECTED` |
| Same relationship after source change | AI_SUGGESTED | prior CONFIRMED | STALE | H1 versus current H2 | original audit retained; review required |
| Exact owner trace link | EXPLICIT | not required | EXPLICIT | trace provenance | owner record remains authority |

## 5. Persistence / Audit

`NEW_DATABASE=NO`. `NEW_TABLE/MODEL=impact_confirmations / ImpactConfirmation`. Rows are immutable decision history in the existing Document Again database. The newest decision is the effective view while all conflicts remain inspectable. Each non-replay mutation creates one existing `audit_events` record: confirmed, rejected, unresolved, or reopened. Audit metadata explicitly records `customer_acceptance=false` and `cross_service_domain_write=false`.

The idempotency key covers project, relationship, candidate, evidence hash, decision, normalized reason, and actor. A unique constraint provides concurrency protection. Identical replays return the original record without a second audit event; competing decisions become separate immutable history rather than overwrites.

## 6. Stale Confirmation

Every decision is version-specific through the reviewer evidence hash, change ID, and relationship contract version. A mutation against a non-current hash returns HTTP 409. Reads derive `STALE` when evidence changes; stale confirmations do not produce `HUMAN_CONFIRMED` effective context. Refresh/review is required.

## 7. Suggested Actions

`impact_actions/v1` is a deterministic read model. It uses explicit tiers (`REQUIRED_ATTENTION`, `RECOMMENDED`, `UNVERIFIED`) and execution modes (`LOCAL_VIEW`, `HUMAN_CONFIRMATION`, `DEEP_LINK`, `DEFERRED_WRITE`). This slice emits only local views and human-decision prompts; no deferred write is executable.

| Impact Type | Suggested Action | Execution Mode | Owner | Implemented? |
| ----------- | ---------------- | -------------- | ----- | ------------ |
| POTENTIALLY_STALE | Review Document | LOCAL_VIEW | Document Again | Yes |
| POTENTIALLY_STALE | Consider New Revision | HUMAN_CONFIRMATION | Document Again | Yes; does not generate |
| EVIDENCE_REVIEW_RECOMMENDED | Review Acceptance Applicability | LOCAL_VIEW | Document Again | Yes |
| Known QA target | Review QA Context | LOCAL_VIEW | QA Again via existing OIDA view | Yes; no mutation |
| Known PM target | Review PM Context | LOCAL_VIEW | PM Again via existing OIDA view | Yes; no mutation |
| Known Infra target | Review Infra Context | LOCAL_VIEW | Infra Again via existing OIDA view | Yes only for known target |
| UNKNOWN | Review Source Evidence | LOCAL_VIEW | Document Again | Yes |
| Any impact | Run tests/change plan/deploy/sign/create CR | DEFERRED_WRITE | Owner service | No |

## 8. UX

The Change Impact surface shows known, possible AI-suggested, and unknown sections separately. Reviewable relationships offer Confirm, Reject, and Leave Unresolved. Reject requires a reason. Current status, actor, staleness, origin class, evidence hash, reason, and full review history are visible. Suggested actions show their execution mode and link only to existing OIDA owner-context routes. Copy explicitly states that recommendations do not execute writes or invalidate acceptance.

## 9. Project Attention Integration

R17.3 actionable stale/acceptance candidates remain the bounded Project Attention contribution. Human confirmation is carried in the impact/reviewer projection and can qualify future high-value attention, but R17.4 does not dump every decision into attention or invent severity.

## 10. Reviewer Integration

Reviewer Change Brief exposes `human_confirmed_impacts`, `rejected_impact_relationships`, and unresolved/stale relationship reviews while retaining deterministic evidence separately. The impact-context hash changes with effective review history, preventing stale AI guidance after a human decision.

## 11. AI Interaction

AI is optional. Future reviewer guidance receives known impacts and effective human reviews. It is instructed to preserve origin, treat `HUMAN_CONFIRMED` only as human project context, and not resurface a same-context rejected relationship. Rejection memory suppresses the same relationship ID at the same evidence hash; materially changed evidence may be reviewed again. No permanent-learning claim is made. AI-suggested submissions require known evidence citations and a target ID present in cited evidence.

## 12. Authorization / Security

Mutation and history endpoints require the existing Account Again actor context and tenant/project guard. The relationship must match the guarded project, retain a recomputable ID/provenance, be reviewable, and use the exact current evidence hash. Explicit/deterministic confirmation attempts fail. Unknown review can reference only privacy-safe `UNRESOLVED:<domain>` placeholders. Production anonymous mutation returns 401. Existing bearer/gateway controls provide the CSRF-resistant API boundary; no cookie-only mutation or owner auth bypass was introduced.

## 13. Tests

Document Again: **169 passed**. Focused impact/reviewer: **33 passed**. Frontend: **10 passed**. Gateway: **3 passed**. Coverage includes confirmation, rejection with required reason, unresolved/reopen, origin retention, effective context, audit metadata, idempotent replay/no audit spam, conflicting immutable decisions, stale evidence rejection/read status, rejection memory, explicit relationship protection, project mismatch/forbidden write, AI grounding, no customer acceptance, no owner mutation, safe action allow/deny lists, AI-not-required behavior, and separated frontend states.

Lint passed with pre-existing warnings. Build passed with the existing bundle-size warning.

## 14. Performance

An isolated local persistence probe measured confirmation plus audit commit at **4.213 ms** (reported **4.210 ms**), confirmation-history load at **0.684 ms**, and action projection at **0.022 ms**. `DOWNSTREAM_CALLS=0`. Impact loading reuses the existing reviewer/impact projection and local database.

## 15. Deployment

Implementation `2c6dc08cbe88d3e67115f0092a1e2a942039855c` passed GitHub CI run `32564929416`. Document Again deployed as Fly release **24**, image `deployment-01M0MCNE4V1RSXB6SPRGTV5SQQ`, machine `185de20c125718`, with one passing check and HTTP 200 health. An in-runtime schema inspection confirmed `impact_confirmations` exists.

OIDA Web deployed as Cloudflare Pages deployment `10acf82c` from the exact implementation SHA. Production serves `index-D3wTbbUm.js` and `index-CJ1VaoTx.css`. Anonymous confirmation mutation returns HTTP 401. The unchanged gateway needed no deployment.

## 16. Operational Backlog

- `OPS-AI-01` Configure authorized production provider.
- `OPS-AI-02` Production AI smoke test.
- `OPS-AUTH-01` Authenticated reviewer dogfood.
- `OPS-AI-03` Authorized-evidence compatibility run.
- `OPS-IMPACT-01` Authenticated R17.3 impact UX dogfood.
- `OPS-AUTH-IMPACT-01` Authenticated confirmation/reject/unresolved/action/history browser dogfood.

## 17. Deferred Cross-Service Writes

- Controlled OIDA-to-PM/QA/Infra mutation routing (R17.5 boundary).
- Owner-service promotion of human-confirmed relationships.
- Test rerun, task/milestone update, infra deployment, document auto-generation, CR creation, approval/sign-off, and acceptance mutation.
- Autonomous remediation or model training/learning.

## 18. Acceptance

```text
IMPACT_CONFIRMATION_CONTRACT=PASS
HUMAN_REVIEW_STATUS=PASS

CONFIRM_RELATIONSHIP=PASS
REJECT_RELATIONSHIP=PASS
UNRESOLVED_RELATIONSHIP=PASS
REOPEN_RELATIONSHIP=PASS

ORIGIN_PROVENANCE=PASS
HUMAN_CONFIRMED_EFFECTIVE_CONTEXT=PASS
STALE_CONFIRMATION=PASS
REJECTION_MEMORY=PASS

AUDIT_TRAIL=PASS
ACTOR_IDENTITY=PASS
IDEMPOTENCY=PASS
CONCURRENCY=PASS

ACTION_RECOMMENDATIONS=PASS
ACTION_EXECUTION_MODES=PASS
DOCUMENT_REVISION_RECOMMENDATION=PASS
QA_REVIEW_RECOMMENDATION=PASS
PM_REVIEW_RECOMMENDATION=PASS
INFRA_REVIEW_RECOMMENDATION=PASS

PROJECT_ATTENTION_INTEGRATION=PASS
REVIEWER_BRIEF_INTEGRATION=PASS
AI_REVIEWER_INTEGRATION=PASS

AI_NOT_CONFIGURED_BEHAVIOR=PASS

LOCAL_CONFIRMATION_WRITES=PASS
CROSS_SERVICE_DOMAIN_WRITES=PASS (0)

PERMISSION_BOUNDARY=PASS
OWNER_MUTATION_PROTECTION=PASS
CUSTOMER_ACCEPTANCE_PROTECTION=PASS

UNIT_TESTS=PASS
INTEGRATION_TESTS=PASS
CONFIRMATION_TESTS=PASS
AUTHORIZATION_TESTS=PASS
FRONTEND_TESTS=PASS
GATEWAY_TESTS=PASS
LINT=PASS
BUILD=PASS

DEPLOYMENT=PASS
PRODUCTION_REVISION_PROOF=PASS
AUTHENTICATED_DOGFOOD=BLOCKED

SECURITY_REGRESSION=PASS
GOVERNANCE_REGRESSION=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS
```

`R17.4 = ACCEPTED_WITH_OPERATIONAL_GAPS`. Product behavior is complete and deployed. Fresh authenticated browser dogfood and provider-backed AI remain operational gaps permitted by the fast-track policy.

---

## OIDA R17.4 — HUMAN-CONFIRMED IMPACT ACTIONS FINAL REPORT

```text
BASELINE_HEAD=84578a08a9b091fa5aff0eb4a11d6e6e6a163845
IMPLEMENTATION_COMMIT=2c6dc08cbe88d3e67115f0092a1e2a942039855c
FINAL_HEAD=ARTIFACT COMMIT (EXACT SHA REPORTED AT HANDOFF)

SOURCE_CODE_CHANGED=YES
WORKTREE_FINAL=CLEAN AND SYNCHRONIZED AT HANDOFF
CI=PASS (32564929416)

DECISION_LITE_RESULT=LOCAL IMMUTABLE CONFIRMATION EVIDENCE IN DOCUMENT AGAIN

IMPACT_CONFIRMATION_CONTRACT=impact_confirmation/v1 PASS
HUMAN_REVIEW_STATUS_MODEL=NOT_REVIEWED, CONFIRMED, REJECTED, UNRESOLVED, DERIVED STALE

CONFIRM_RELATIONSHIP=PASS
REJECT_RELATIONSHIP=PASS
UNRESOLVED_RELATIONSHIP=PASS
REOPEN_RELATIONSHIP=PASS

ORIGIN_PROVENANCE=PASS
HUMAN_CONFIRMED_EFFECTIVE_CONTEXT=PASS
STALE_CONFIRMATION=PASS
REJECTION_MEMORY=PASS

AUDIT_TRAIL=PASS
ACTOR_IDENTITY=ACCOUNT AGAIN / EXISTING ACTOR CONTEXT
IDEMPOTENCY=PASS
CONCURRENCY=PASS (UNIQUE IDEMPOTENCY CONSTRAINT + IMMUTABLE CONFLICT HISTORY)

ACTION_RECOMMENDATIONS=impact_actions/v1 PASS
ACTION_EXECUTION_MODES=LOCAL_VIEW, HUMAN_CONFIRMATION; DEEP_LINK/DEFERRED_WRITE FUTURE-SAFE

DOCUMENT_ACTIONS=REVIEW + CONSIDER REVISION; NO GENERATION
PM_ACTIONS=REVIEW CONTEXT ONLY
QA_ACTIONS=REVIEW CONTEXT ONLY
INFRA_ACTIONS=REVIEW KNOWN CONTEXT ONLY
GOVERNANCE_ACTIONS=REVIEW ACCEPTANCE APPLICABILITY ONLY

PROJECT_ATTENTION_INTEGRATION=PASS
REVIEWER_BRIEF_INTEGRATION=PASS
AI_REVIEWER_INTEGRATION=PASS

AI_PROVIDER_RUNTIME=AI_NOT_CONFIGURED / OPERATIONAL BACKLOG
AI_NOT_CONFIGURED_BEHAVIOR=CONFIRMATION AND DETERMINISTIC ACTIONS REMAIN AVAILABLE

LOCAL_CONFIRMATION_WRITES=impact_confirmations + audit_events
CROSS_SERVICE_DOMAIN_WRITES=0
AUTONOMOUS_ACTIONS=0

PERMISSION_BOUNDARY=PASS
OWNER_MUTATION_PROTECTION=PASS
CUSTOMER_ACCEPTANCE_PROTECTION=PASS

CONFIRMATION_LATENCY=4.213 ms LOCAL PROBE
IMPACT_LOAD_LATENCY=0.684 ms CONFIRMATION-HISTORY PROBE
DOWNSTREAM_CALLS=0

DOCUMENT_TESTS=169 PASS
IMPACT_TESTS=PASS
CONFIRMATION_TESTS=PASS
AUTHORIZATION_TESTS=PASS
AI_SAFETY_TESTS=PASS
FRONTEND_TESTS=10 PASS
GATEWAY_TESTS=3 PASS
LINT=PASS WITH PRE-EXISTING WARNINGS
BUILD=PASS WITH EXISTING BUNDLE WARNING

DEPLOYMENT=PASS
PRODUCTION_REVISION_PROOF=FLY RELEASE 24 + PAGES 10acf82c + SOURCE 2c6dc08
AUTHENTICATED_DOGFOOD=OPERATIONAL_BACKLOG

SECURITY_REGRESSION=PASS
GOVERNANCE_REGRESSION=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS

OPERATIONAL_BACKLOG:
- OPS-AI-01
- OPS-AI-02
- OPS-AUTH-01
- OPS-AI-03
- OPS-IMPACT-01
- OPS-AUTH-IMPACT-01

DEFERRED:
- Cross-service domain writes
- Controlled mutation routing
- Human-confirmed relationship promotion into owner services
- Autonomous remediation

R17_4=ACCEPTED_WITH_OPERATIONAL_GAPS
NEXT_STEP=R17.5 CONTROLLED CROSS-SERVICE ACTION ROUTING; DO NOT IMPLEMENT IN R17.4
```
