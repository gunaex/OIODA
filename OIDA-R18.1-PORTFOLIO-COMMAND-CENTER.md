# OIDA R18.1 — Portfolio Command Center

## 1. Baseline
Baseline `03f272240212f8554f77c342b940a35d0b8bfac1` is accepted R18.2.

## 2. Decision-Lite Findings
Portfolio composes active projects already filtered by the current authenticated tenant scope. It reuses `project_command_center/v1` and `project_briefing/v1`, adds no owner writes, and uses a separate portfolio checkpoint.

## 3. Portfolio Architecture
`Project Command Center → Project Briefing × authorized active projects → portfolio_command_center/v1`. Project failures are isolated. Cards contain bounded summaries; detailed history remains on drill-down.

## 4. Authorization Scope
The server obtains the active project set under the existing authenticated tenant context before composition. Unauthorized projects are never loaded, counted, titled, cited, or sent to AI. Removed access disappears immediately.

## 5. Portfolio Contract
`portfolio_command_center/v1` includes project summaries, explainable attention, focus projects, unverified projects, `portfolio_briefing/v1`, project-scoped evidence, partial status, provenance, and performance.

## 6. Project Prioritization
Deterministic tuple: P1 blocked/reopened; P2 recheck/new attention; P3 waiting; P4 recorded change; P5 informational. No numeric score or inferred commercial importance.

| Project | Current State | New Attention | Waiting | Reopened | Unverified | Priority Tier | Reason |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| Fixture B | BLOCKED | 0 | 0 | 0 | 0 | P1 | blocker evidence |
| Fixture A | ATTENTION | 1 | 0 | 0 | 0 | P2 | new attention |
| Fixture C | ATTENTION | 0 | 1 | 0 | 0 | P3 | waiting evidence |

## 7. Portfolio Attention
Blocked, attention, waiting, and unverified counts are labelled project counts rather than summed raw issue counts.

## 8. Portfolio Briefing
`portfolio_briefing/v1` aggregates project briefing semantics for changes, waiting, resolved, reopened, focus, and scope changes. First view is explicitly current portfolio state.

## 9. Portfolio Review Checkpoint
`portfolio_review_checkpoints` stores per-user scope, per-project cutoffs, exact evidence-version cursor maps, and included projects. Mark Reviewed is explicit and idempotent.

```text
Generated: A100 / B200 / C300
Late: A101 / C301
Mark Reviewed stores: A100 / B200 / C300
Remaining unseen: A101 / C301
```

## 10. Project Checkpoint Independence
Portfolio acknowledgement never writes `project_review_checkpoints`; regression coverage proves detailed project cursors remain unchanged.

## 11. Waiting / Resolved / Reopened
These states come from project briefing/resolution contracts and remain distinct. Resolved progress is below active risk; reopened evidence receives P1.

## 12. New / Removed Project Scope
Projects newly present after a checkpoint are `FIRST_SEEN`, a portfolio-scope change rather than a business change. Removed projects disappear from summaries/evidence immediately; only opaque removed IDs appear in the current user's scope-change metadata.

## 13. Grounded Portfolio Copilot
`portfolio_copilot/v1` uses project-prefixed evidence IDs (`project_id:evidence_id`), deterministic focus, and the shared provider readiness boundary. With AI unconfigured it remains fully useful; configured narrative stays conservatively deterministic until the project-scoped comparison validator is enabled. Auto-execution is zero.

| User Question | Project(s) Mentioned | Evidence IDs | Supported | Limitations |
| --- | --- | --- | --- | --- |
| Focus across projects | authorized focus projects | project-prefixed | Yes | delivery evidence only |
| Which are blocked? | authorized P1 projects | project-prefixed blockers | Yes | partial projects disclosed |
| What changed? | authorized recorded changes | project-prefixed CHG IDs | Yes | no inferred history |

## 14. Security / Cross-Project Isolation
Tests prove an excluded project name is absent from the entire payload and citation set. Actor-scoped checkpoint APIs cannot select another user. No bulk action or acceptance endpoint exists.

## 15. Performance / Bounded Concurrency
Concurrency is explicitly 1 because a shared SQLAlchemy session and nested project owner fan-out are not thread-safe. Project count is capped at 50; tests cover 1/5/20/50. Endpoint reports project count, latency, downstream calls, failures, concurrency, and limit.

## 16. UX
The Projects page adds a responsive Portfolio Command Center with labelled project-state counts, focus cards, project drill-down, independent Mark Portfolio Reviewed, and grounded Copilot fallback.

## 17. Tests
Document Again **202 passed**; portfolio **8 passed**; frontend **11 passed**; gateway **3 passed**. Coverage includes authorization set, scale, priority, partial failure, race-safe checkpoint, project independence, first-seen, access removal, scoped citations, and AI absence.

## 18. Deployment
Pending CI and production rollout.

## 19. Operational Backlog
- Carry forward prior operational items.
- `OPS-PORTFOLIO-01`: authenticated multi-project browser dogfood.
- Enable validated provider narrative when production AI is configured.

## 20. Deferred Scope
Cross-project causal intelligence, bulk actions, scheduled delivery, financial/resource optimization, and autonomous remediation remain deferred.

## 21. Acceptance
```text
PORTFOLIO_COMMAND_CENTER_CONTRACT=portfolio_command_center/v1
PORTFOLIO_BRIEFING_CONTRACT=portfolio_briefing/v1
PORTFOLIO_REVIEW_CHECKPOINT=portfolio_review_checkpoint/v1
AUTHORIZED_PROJECT_SCOPE=PASS_ACTIVE_TENANT_SCOPE_FIRST
CROSS_PROJECT_ISOLATION=PASS
PROJECT_SUMMARIES=PASS
PROJECT_PRIORITIZATION=PASS
PRIORITY_EXPLAINABILITY=PASS_NO_SCORE
BLOCKED_PROJECTS=PASS
ATTENTION_PROJECTS=PASS
WAITING_PROJECTS=PASS
UNVERIFIED_PROJECTS=PASS
RECENTLY_CHANGED=PASS_RECORDED_ONLY
RECENTLY_RESOLVED=PASS
REOPENED=PASS
PORTFOLIO_FIRST_REVIEW=PASS
SINCE_LAST_PORTFOLIO_REVIEW=PASS
RACE_SAFE_PORTFOLIO_CHECKPOINT=PASS
PROJECT_CHECKPOINT_INDEPENDENCE=PASS
NEW_PROJECT_SCOPE=FIRST_SEEN
REMOVED_PROJECT_SCOPE=REMOVED_IMMEDIATELY
PORTFOLIO_COPILOT=portfolio_copilot/v1
COPILOT_PROJECT_SCOPED_CITATIONS=PASS
COPILOT_GROUNDING=DETERMINISTIC
COPILOT_UNAUTHORIZED_PROJECT_GUARD=PASS
COPILOT_CUSTOMER_ACCEPTANCE_GUARD=PASS_NO_ACCEPTANCE_INFERENCE
COPILOT_AUTO_EXECUTION=0
PARTIAL_PROJECT_BEHAVIOR=PASS
BOUNDED_CONCURRENCY=1
PROJECT_COUNT_SCALE_TESTS=1_5_20_50_PASS
NEW_OWNER_ACTION_TYPES=0
AUTONOMOUS_ACTIONS=0
NEW_DATABASE=NO
NEW_TABLE=portfolio_review_checkpoints
```
