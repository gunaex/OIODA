# OIDA R18 — Project Command Center + Grounded AI Copilot MVP

## 1. Baseline

Baseline `8e1a359ebaede064b0dc069f368384001dfe3644` is the accepted R17.6 release. R18 composes its truth, attention, impact, action, resolution, governance, and acceptance foundations without reopening or replacing them.

## 2. Decision-Lite Findings

The existing project home independently fetched seven Document views plus truth. The minimal coherent evolution is one authenticated `project_command_center/v1` composition endpoint and one non-blocking `project_copilot/v1` query endpoint over the same curated evidence catalog. No owner action, database, authority, or workflow was added.

## 3. Command Center Architecture

`project_truth/v1` is fetched once and already performs bounded parallel PM/QA/Infra reads with partial-service isolation. The server then composes local recorded change history, human impact confirmations, controlled action history, deterministic resolution history, current document governance, and version-specific acceptance evidence. React consumes the resulting projection rather than repeating the former heavy project-home batch.

## 4. Command Center Contract

`project_command_center/v1` contains project identity, explainable health, current attention, delivery, recent changes, active impacts, action summary, resolution summary, governance, acceptance, waiting-on, history, `project_command_context/v1`, freshness, warnings, provenance, and performance. It is derived and non-authoritative; its source contracts remain authoritative in their established scopes.

| UI Area | Source Contract | Key Fields | Authority | Degraded State |
| ------- | --------------- | ---------- | --------- | -------------- |
| Project Health | `project_truth/v1`, `project_attention/v1`, `impact_resolution/v1` | source status, attention counts, active/waiting | derived from owner/rule truth | explicit `UNAVAILABLE`, `UNBOUND`, `UNKNOWN` |
| Attention | `project_attention/v1` | blocker, issue, unverified, stable item ID | deterministic projection | unavailable sources remain unverified |
| Changes | recorded timeline / `project_change/v1` semantics | ID, type, summary, timestamp | recorded history | empty is “no recorded changes,” not proof of no change |
| Impacts | `impact_confirmation/v1` | origin class, decision, evidence context | human-confirmed context | stale/unresolved remains visible |
| Actions | `action_route/v1` | allowlisted type, owner, route state/result | orchestration evidence | failure/unknown result shown verbatim |
| Resolution | `impact_resolution/v1` | state, rule, reason, evidence, history | deterministic rule projection | blocked/unknown/recheck remain active |
| Governance | Document governance | readiness, freshness, lifecycle | Document Again | flags shown, never inferred clear |
| Acceptance | version-specific signoff evidence | class, purpose, decision, version | Document Again | TEST/INTERNAL never becomes CUSTOMER |
| Copilot | `project_command_context/v1` | curated evidence IDs and source labels | advisory explanation only | deterministic fallback remains available |

## 5. Project Health

Health is explainable categorical state, not a score: Delivery attention, QA source/readiness, Infra source/readiness, governance flag count, and active/waiting resolution counts. Evidence IDs provide the reasons.

## 6. Attention

The primary counts remain exactly `project_attention/v1` blocker/issue/unverified counts. Impact and resolution are labelled workload and are not added to blocker totals, preventing the same QA root issue from appearing as three blockers.

## 7. Changes

Recent Changes uses recorded project timeline entries normalized to stable `CHG-*` evidence. Missing history is stated as no recorded recent changes; it is never fabricated or interpreted as unchanged.

## 8. Impacts

Current effective human relationship reviews retain origin classification and evidence context. Known, suggested, confirmed, rejected, stale, and unresolved semantics remain distinct in their source contracts; the Command Center does not promote AI suggestions.

## 9. Actions

The workspace shows executing, succeeded, failed, and unknown-result routes and exposes only the existing PM/QA action registry. Copilot action pointers are always non-executable and lead to the unchanged preview/explicit-human-execute UI.

## 10. Resolution

Active resolution includes `OPEN`, `ACTION_PLANNED`, `ACTION_IN_PROGRESS`, `WAITING_ON_OWNER`, `RECHECK_REQUIRED`, `BLOCKED`, and `UNKNOWN`. Resolved/inapplicable states are removed from current work and retained under Recently Resolved/history.

## 11. Governance / Acceptance

Current readiness/freshness flags and signoff evidence remain version-specific. `customer_accepted` requires CUSTOMER/FORMAL_EXTERNAL evidence, ACCEPTANCE/SIGN_OFF purpose, and a qualifying decision. TEST approval cannot satisfy it.

## 12. AI Copilot

`project_copilot/v1` supports `FOCUS_TODAY`, `PROJECT_STATUS`, `WHAT_CHANGED`, `WHAT_IS_BLOCKED`, `WHAT_IS_WAITING`, `WHAT_IS_UNRESOLVED`, and `WHY_IS_THIS_NOT_READY`. Each request rebuilds current project context. Deterministic matching runs before AI and remains the answer when AI is absent or fails. No conversation memory or tool execution was added.

## 13. Citation / Grounding

Evidence IDs resolve to source label, summary, authority, and structured data. Unknown citations, uncited claims, unknown actions, false resolution, and unsupported customer acceptance are withheld. Project/document content is serialized as untrusted evidence. AI is not presented as the source.

| User Question | AI Answer Summary | Evidence IDs | Supported | Action Offered |
| ------------- | ----------------- | ------------ | --------- | -------------- |
| What should I focus on today? | Current QA blocker, waiting resolution, governance gap | `ATTN-qa-root`, `RES-*`, `GOV-*` | Yes | controlled QA route may be linked for review only |
| What is blocked? | Only `BLOCKER` attention and `BLOCKED` resolution | `ATTN-qa-root` | Yes | None in fixture |
| What changed? | Recorded timeline events only | `CHG-*` | Yes when history exists | None |

## 14. UX

Above the fold presents five health categories, deduplicated attention, and the Copilot. Progressive sections show changes, impacts, actions, open/waiting resolution, Waiting On, governance/acceptance, and Recently Resolved. Semantic headings, labelled input, keyboard buttons, textual statuses, and citation disclosure preserve accessibility. The responsive grid collapses at narrow widths.

## 15. Tests

Document Again: **187 passed**. Command Center/Copilot: **7 passed**. Frontend: **11 passed**. Gateway: **3 passed**. Coverage includes representative composition, partial QA failure, Infra unbound, deduplication, resolved exclusion, AI-not-configured, provider failure fallback, citations, unknown action rejection, false resolution, customer acceptance protection, and non-execution.

## 16. Performance

The response exposes Command Center latency, truth latency, downstream-call count, and `extra_owner_calls=0`. Composition adds indexed/local reads after the single existing truth fan-out. Copilot latency is separate. No cache, materialized source, polling process, or new database was introduced.

## 17. Deployment

Implementation `3528c036fdd547461ecff6fe7bb5a363698fb0b4` passed CI run `32567045991`. Document Again deployed as Fly release **27**, image `deployment-01M0MFC39554JVZ9E5RD5RN7Q4`, with one passing check and HTTP 200 health.

OIDA Web production deployment is Cloudflare Pages `26d1156b`, sourced from `3528c03`, serving `index-Br4fV86Q.js` and `index-sfLoufqr.css`. Anonymous Command Center and Copilot calls both return HTTP 401. Owner services, Conductor, Account, and Gateway were unchanged and not redeployed.

## 18. Operational Backlog

- Carry forward consolidated `OPS-AI-01`, `OPS-AI-02`, `OPS-AI-03`, `OPS-AUTH-01`, `OPS-ACTION-01`, and `OPS-RESOLUTION-01`.
- Authenticated Command Center/Copilot browser dogfood if a safe session is unavailable.
- Existing owner deep-link SSO continuity and narrow fixed-sidebar work remain operational UX items.

## 19. Deferred Scope

Portfolio Command Center, daily push briefing, autonomous remediation, automatic owner actions, Infra execution, generic company chat, long-term memory, universal workflow, and customer acceptance automation remain deferred. New owner action types: **0**. New database: **NO**.

## 20. Acceptance

```text
PROJECT_COMMAND_CENTER_CONTRACT=PASS
PROJECT_HEALTH=PASS_EXPLAINABLE_NO_SCORE
PROJECT_ATTENTION=PASS
RECENT_CHANGES=PASS_RECORDED_ONLY
ACTIVE_IMPACTS=PASS
ACTIVE_ACTIONS=PASS
RESOLUTION_SUMMARY=PASS
GOVERNANCE_SUMMARY=PASS
ACCEPTANCE_SUMMARY=PASS
WAITING_ON=PASS_EVIDENCE_ONLY
RECENTLY_RESOLVED=PASS
NEEDS_MY_ATTENTION=NOT_DETERMINED_NO_ASSIGNMENT_GUESS
DEDUPLICATION=PASS_STABLE_EVIDENCE_ID
PARTIAL_SERVICE_BEHAVIOR=PASS
FRESHNESS=PASS
PROVENANCE=PASS
PROJECT_COPILOT=project_copilot/v1
FOCUS_TODAY=PASS
PROJECT_STATUS_QUERY=PASS
WHAT_CHANGED_QUERY=PASS
WHAT_BLOCKED_QUERY=PASS
WHAT_UNRESOLVED_QUERY=PASS
COPILOT_CITATIONS=PASS
COPILOT_GROUNDING=PASS
COPILOT_UNKNOWN_HANDLING=PASS
COPILOT_ACTION_ALLOWLIST=PASS
COPILOT_AUTO_EXECUTION=0
AI_PROVIDER_RUNTIME=OPTIONAL
AI_NOT_CONFIGURED_BEHAVIOR=PASS_DETERMINISTIC_FALLBACK
AI_FAILURE_FALLBACK=PASS
CUSTOMER_ACCEPTANCE_PROTECTION=PASS
AI_AUTHORITY_BOUNDARY=NONE
NEW_OWNER_ACTION_TYPES=0
AUTONOMOUS_ACTIONS=0
NEW_DATABASE=NO
COMMAND_CENTER_LATENCY=RESPONSE_MEASURED
DOWNSTREAM_CALLS=EXISTING_PROJECT_TRUTH_FAN_OUT; EXTRA_OWNER_CALLS_0
COPILOT_LATENCY=SEPARATE_RESPONSE_MEASURED
DOCUMENT_TESTS=187_PASS
COMMAND_CENTER_TESTS=7_PASS
COPILOT_TESTS=7_PASS_FOCUSED_SUITE
AI_SAFETY_TESTS=PASS
FRONTEND_TESTS=11_PASS
GATEWAY_TESTS=3_PASS
LINT=PASS_WITH_PRE_EXISTING_WARNINGS
BUILD=PASS_WITH_PRE_EXISTING_BUNDLE_WARNING
DEPLOYMENT=PASS_DOCUMENT_RELEASE_27_AND_WEB_26D1156B
PRODUCTION_REVISION_PROOF=PASS
AUTHENTICATED_DOGFOOD=OPERATIONAL_GAP
SECURITY_REGRESSION=PASS
GOVERNANCE_REGRESSION=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS
R18=ACCEPTED_WITH_OPERATIONAL_GAPS
```
