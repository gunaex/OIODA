# OIDA R18.2 — Grounded Daily Project Briefing

## 1. Baseline

Baseline `9272bdda7fe2958e7b52eb38ee964ab341b8eb53` is the accepted R18 Command Center release.

## 2. Decision-Lite Findings

The briefing is a projection over `project_command_center/v1`. One OIDA-owned per-user/project checkpoint is required for cross-device, explicit acknowledgement. Page loads, refreshes, and AI calls are read-only.

## 3. Briefing Architecture

The Command Center composes owner truth once and passes the same in-memory projection to `project_briefing/v1`; briefing composition adds zero owner calls. An on-demand endpoint can produce the same future-ready contract. No scheduler or notification system was added.

## 4. Review Checkpoint Model

`project_review_checkpoints` uniquely keys project and user, storing reviewed-through cutoff, exact evidence-version cursors, briefing cursor, source, and acknowledgement time. Updates emit one `PROJECT_BRIEFING_REVIEWED` audit event; identical acknowledgements are idempotent.

## 5. Briefing Contract

`project_briefing/v1` contains project/user context, mode, reproducible window, checkpoint, changed/new/still-open/waiting/resolved/reopened typed items, decision attention, health, deterministic focus, evidence, freshness, limitations, mark-reviewed payload, and performance.

## 6. Briefing Window Semantics

First view is labelled `FIRST_VIEW_CURRENT_BRIEF`, never “since last review.” Later windows use the explicit checkpoint cutoff through the generated briefing cutoff. Evidence cursors combine stable ID and normalized data hash, detecting a root that returns with changed state.

Race trace:

```text
Previous checkpoint: E10
Briefing cutoff: E15 / T15
Events included: E11–E15
Events excluded: <=E10
Late event: E16 arrives after T15
Final checkpoint after Mark Reviewed: exact T15 visible evidence set
Next brief: E16 remains new
```

## 7. Changed Since Last Review

Only recorded `CHG-*` events whose timestamps fall strictly after the checkpoint and at/before cutoff are classified `CHANGED`. Missing history produces `PARTIAL_HISTORY` rather than a false “nothing changed” claim.

## 8. New Attention

Current attention whose evidence-version cursor was not visible at the checkpoint is `NEW`. First-view attention is `CURRENT_ATTENTION`, not fabricated new history.

## 9. Still Open

Previously reviewed attention, active resolution, and governance flags that remain current are `STILL_OPEN`. No-change briefings continue to show them.

## 10. Waiting On

Only `WAITING_ON_OWNER` resolution evidence enters `WAITING`; no person is guessed. Neutral state is shown without invented SLA or deadline.

## 11. Resolved / Reopened

Immutable resolution events within the window produce `RESOLVED` or prominent P1 `REOPENED` items. Action success alone is never resolution, and resolution never implies customer acceptance.

## 12. Deterministic Focus Today

Rules use explicit tiers: P1 blocker/reopened, P2 recheck/new governance or impact, P3 waiting/still-open review, P4 recorded change, P5 resolved context. Focus is capped at seven and resolved items cannot outrank active work.

## 13. AI Briefing

`project_briefing_ai/v1` reuses the hardened reviewer provider adapter. It summarizes only the bounded briefing packet. Unknown citations/actions, “new” claims outside the window, false resolution, and unsupported customer acceptance are rejected. Provider absence/failure returns the complete deterministic briefing and never changes checkpoint state.

## 14. Command Center Integration

The briefing is the first Command Center layer, above health. It includes counts/sections, Focus Today, an explicit keyboard-accessible Mark Reviewed action, and collapsible evidence-grounded sections. Collapse does not acknowledge.

## 15. Authorization / Multi-Device

Existing project authentication guards both read and update. Actor identity supplies the user key; clients cannot select another user. Server persistence gives multi-device consistency. Project unique scope prevents cross-project clearing.

## 16. Tests

Document Again **194 passed**; focused Command Center/briefing **14 passed**; frontend **11 passed**; gateway **3 passed**. Coverage includes creation, idempotency, race safety, user/project isolation, no-change still-open, partial service, unbound Infra, resolved/reopened, AI absence, time-window guard, resolution guard, action allowlist, and deterministic fallback.

## 17. Performance

Briefing and checkpoint update latency are response-measured. Embedded Command Center briefing adds `NEW_OWNER_CALLS=0`; AI latency is separate. History is bounded and checkpoint access is indexed.

## 18. Deployment

To be completed after CI and production rollout.

## 19. Operational Backlog

- Carry forward consolidated AI/auth/action/resolution operational items.
- `OPS-BRIEF-01`: authenticated initial-review/race-window browser dogfood.

## 20. Future Portfolio Reuse

The project/user/window-neutral contract can later be scheduled or aggregated, but scheduled delivery, notifications, and Portfolio remain deferred.

## 21. Acceptance

| Briefing Item | Time Classification | Root Evidence | Current State | User-Specific? | Citation |
| --- | --- | --- | --- | --- | --- |
| QA blocker first view | `CURRENT_ATTENTION` | stable attention ID + fact hash | `BLOCKER` | checkpoint classification yes | `ATTN-*` |
| QA waiting before checkpoint | `WAITING` | impact candidate/resolution | `WAITING_ON_OWNER` | checkpoint classification yes | `RES-*` |
| Resolution event after checkpoint | `RESOLVED` | immutable resolution event | `RESOLVED` | window yes | `RES-*` |
| Returned impact after resolution | `REOPENED` | immutable reopen event | active state | window yes | `RES-*` |

```text
PROJECT_BRIEFING_CONTRACT=project_briefing/v1
REVIEW_CHECKPOINT_MODEL=project_review_checkpoint/v1
NEW_TABLE=project_review_checkpoints
NEW_DATABASE=NO
FIRST_REVIEW=PASS
SINCE_LAST_REVIEW=PASS
BRIEFING_WINDOW=PASS
RACE_SAFE_CHECKPOINT=PASS
CHANGED_SINCE_REVIEW=PASS_RECORDED_ONLY
NEW_ATTENTION=PASS
STILL_OPEN=PASS
WAITING_ON=PASS
RESOLVED_SINCE_REVIEW=PASS
REOPENED=PASS
DETERMINISTIC_FOCUS_TODAY=PASS
DEDUPLICATION=PASS_STABLE_ROOT
PARTIAL_HISTORY=PASS
PARTIAL_SERVICE_BEHAVIOR=PASS
USER_SPECIFIC_CHECKPOINT=PASS
MULTI_PROJECT_ISOLATION=PASS
MULTI_DEVICE_PERSISTENCE=PASS_SERVER_SIDE
MARK_REVIEWED=EXPLICIT_ONLY
CHECKPOINT_IDEMPOTENCY=PASS
AUTHORIZATION=PASS_EXISTING_PROJECT_AND_ACTOR_BOUNDARY
AI_BRIEFING=project_briefing_ai/v1
AI_CITATIONS=PASS
AI_TIME_WINDOW_GROUNDING=PASS
AI_RESOLUTION_GUARD=PASS
AI_CUSTOMER_ACCEPTANCE_GUARD=PASS
AI_NOT_CONFIGURED_BEHAVIOR=PASS
AI_FAILURE_FALLBACK=PASS
COMMAND_CENTER_INTEGRATION=PASS
COPILOT_INTEGRATION=PASS_SHARED_PROVIDER_AND_EVIDENCE
NEW_OWNER_CALLS=0
SCHEDULED_DELIVERY=DEFERRED
```
