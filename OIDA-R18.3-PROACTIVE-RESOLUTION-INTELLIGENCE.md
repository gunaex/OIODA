# OIDA R18.3 — Proactive Resolution Intelligence

## 1. Baseline and Decision

R18.3 extends the accepted R18.1 Portfolio Command Center and R18.2 Daily Project Briefing. The implementation is a deterministic, read-only projection over existing `impact_resolution/v1` and `action_route/v1` truth. It adds no database, table, owner call, scheduler, notification, autonomous action, or owner-side write.

## 2. Architecture

```text
owner truth → project_command_center/v1
                    ↓ existing active impact resolutions and action routes
             resolution_intelligence/v1
                    ├── project resolution focus
                    ├── project_briefing/v1 resolution_focus
                    └── portfolio_command_center/v1 resolution summary
```

The projection operates on the already composed Command Center packet, so its reported `extra_owner_calls` is zero. The dedicated project endpoint returns the same embedded packet rather than recomposing independently.

## 3. Contract

`resolution_intelligence/v1` exposes unresolved and focus items, blocked/waiting/recheck/unknown groups, recommended supported next steps, provenance, limitations, and measured projection latency. Each item includes:

- stable intelligence, project, resolution, impact, and confirmation IDs;
- current state and deterministic reason class;
- explainable P1–P5 priority tier, with no numeric or opaque score;
- neutral time in state, without deadline or SLA inference;
- the existing resolution registry's required authoritative truth;
- safe existing next steps and explicit action readiness;
- evidence IDs, rule ID/version, reopening status, and recorded-transition metadata;
- explicit `customer_acceptance=false` and `autonomous=false` safeguards.

## 4. Reason Classes

The closed classification set is `WAITING_FOR_OWNER`, `MISSING_EVIDENCE`, `STALE_EVIDENCE`, `OWNER_UNAVAILABLE`, `MISSING_BINDING`, `AUTHORIZATION_REQUIRED`, `ACTION_REQUIRED`, `REVIEW_REQUIRED`, `CONFLICT`, and `UNKNOWN`.

`BLOCKED` and `WAITING_ON_OWNER` remain distinct. Missing owner evidence is waiting, not blocked. Missing binding, authorization failure, or unavailable owner truth can block. `RECHECK_REQUIRED` is stale-evidence attention and never implies resolution.

## 5. What Would Resolve This

The projection reads `impact_resolution_rules/v1` directly. PM handoffs require matching PM owner truth explicitly complete/resolved. QA handoffs require an OK QA source, complete validation evidence, and no remaining failed, blocked, or blocking validation truth. Unknown action types disclose that no deterministic resolution condition is registered.

Action success alone never closes an impact. Resolution remains owned by the deterministic evaluator after authoritative recheck.

## 6. Safe Next Steps and Readiness

Only existing allowlisted action types and the read-only `RECHECK` operation can be suggested. Existing routed actions remain `HUMAN_PREVIEW_EXECUTE` and are never executable from the intelligence response. Unsupported cases return `ACTION_NOT_SUPPORTED`; no invented action is substituted.

## 7. Priority and Time

- P1: blocked, reopened, missing binding, or authorization required.
- P2: recheck required, stale evidence, or conflict.
- P3: open/action planned.
- P4: waiting on owner/action in progress.
- P5: remaining informational/unknown review.

Time in state is elapsed recorded time only. It has no scoring weight and creates no urgency, SLA, or deadline claim.

## 8. Grounded AI Assistant

`resolution_intelligence_ai/v1` is optional and advisory. With no provider it returns the complete deterministic focus. With a provider it sends only the bounded unresolved packet, requires evidence citations, validates action types against the existing registry plus `RECHECK`, and rejects unknown citations, false resolution, unsupported customer acceptance, and invented actions. AI authority and auto-execution remain zero. Provider failure preserves deterministic output.

## 9. Product Integration

The Project Command Center shows a Resolution Focus card with unresolved, blocked, waiting, and recheck counts plus why, resolution truth, next step, time, and citations. Daily briefing exposes the same `resolution_focus`; Portfolio cards use the same intelligence classifications and expose bounded resolution counts/focus. Existing detailed Deliverables and History routes remain the drill-down and action surfaces.

## 10. API

- `GET /api/projects/{project_id}/resolution-intelligence`
- `POST /api/projects/{project_id}/resolution-intelligence/assistant`

Both retain the existing authenticated project boundary. They do not accept actor-selected state changes or action payloads.

## 11. Test Evidence

Document Again: **210 passed**. Focused resolution/Command Center/briefing/portfolio: **30 passed**. OIDA Web: **11 passed** and production build passed. Gateway: **3 passed**. Coverage includes state distinctions, reason classification, registry truth, P1–P5 priority, reopening, neutral time, partial packets, zero extra calls, AI absence, citations, allowlist, false-resolution/customer-acceptance rejection, and non-executable advice.

The Vite production build retains the pre-existing bundle-size advisory; it is not a build failure.

## 12. Deployment

Implementation `9f9c053` was pushed to `main`. Document Again deployed as Fly release **30**, image `deployment-01M0MJ27Q04Q812N3D1680P59F`, with its machine started and one of one checks passing. The direct health endpoint returned HTTP 200.

OIDA Web deployed as Cloudflare Pages production revision `5e2d20d0-5c51-46bb-816e-88ea79c4104c`, sourced from exact SHA `9f9c053`. The custom domain returned HTTP 200 and served `index-D1RE15WR.js` and `index-CiWTekrW.css`. Anonymous deterministic-intelligence GET and assistant POST calls both returned HTTP 401 at the unchanged deny-by-default gateway.

Account, PM, QA, Infra, Conductor, and Gateway were unchanged and not redeployed. Authenticated representative-project browser dogfood remains an operational follow-up because no fresh human session was available in this execution context; no credential extraction or authentication bypass was attempted.

## 13. Deferred Scope

New owner actions, autonomous remediation, scheduled monitoring, notifications, SLA/deadline inference, commercial priority inference, database persistence, cross-project causal inference, and bulk execution remain deferred.

## 14. Acceptance

```text
RESOLUTION_INTELLIGENCE_CONTRACT=resolution_intelligence/v1
RESOLUTION_AI_CONTRACT=resolution_intelligence_ai/v1
DERIVED_FROM_IMPACT_RESOLUTION=PASS
BLOCKED_VS_WAITING=PASS_DISTINCT
REASON_CLASSES=PASS_CLOSED_SET
WHAT_WOULD_RESOLVE_THIS=PASS_RULE_REGISTRY
SAFE_NEXT_STEPS=PASS_EXISTING_ACTIONS_PLUS_RECHECK
ACTION_READINESS=PASS
PRIORITY=PASS_P1_TO_P5_NO_SCORE
TIME_IN_STATE=PASS_NEUTRAL
REOPENED=PASS_P1
PARTIAL_TRUTH=PASS
COMMAND_CENTER_INTEGRATION=PASS
DAILY_BRIEFING_INTEGRATION=PASS
PORTFOLIO_INTEGRATION=PASS
AI_GROUNDING=PASS
AI_CITATIONS=PASS
AI_ACTION_ALLOWLIST=PASS
AI_FALSE_RESOLUTION_GUARD=PASS
AI_CUSTOMER_ACCEPTANCE_GUARD=PASS
AI_AUTHORITY=NONE
AUTO_EXECUTION=0
NEW_OWNER_ACTION_TYPES=0
NEW_OWNER_CALLS=0
NEW_DATABASE=NO
NEW_TABLE=NO
SCHEDULER=NO
NOTIFICATIONS=NO
DOCUMENT_TESTS=210_PASS
RESOLUTION_FOCUSED_TESTS=30_PASS
FRONTEND_TESTS=11_PASS
GATEWAY_TESTS=3_PASS
BUILD=PASS_WITH_PRE_EXISTING_BUNDLE_WARNING
DEPLOYMENT=PASS_DOCUMENT_RELEASE_30_AND_WEB_5E2D20D0
PRODUCTION_HEALTH=PASS
PRODUCTION_REVISION_PROOF=PASS
ANONYMOUS_AUTH_GUARD=PASS_HTTP_401_GET_AND_POST
AUTHENTICATED_PROJECT_DOGFOOD=OPERATIONAL_BACKLOG
R18_3=ACCEPTED_WITH_OPERATIONAL_GAPS
```
