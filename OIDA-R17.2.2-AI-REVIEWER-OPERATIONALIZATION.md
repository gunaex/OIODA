# OIDA R17.2.2 — AI Reviewer Quality & Operationalization

Date: 2026-08-22 (Asia/Bangkok)

Baseline: `4d4d160b51aa7d90170ef19e9ac5be6c12e7f9b2`

Implementation commit: `26994961eace56a94d2ea4699235577f08398e83`

Decision: `ACCEPTED_WITH_OPERATIONAL_GAPS`

## 1. Baseline

R17.2.1 is accepted with operational gaps. Its immutable evidence packet, deterministic change brief, AI reviewer contract, document diff, evidence IDs, responsibility/governance model, safety guards, cache/stale behavior, and human authority boundary were reused. The three starting operational gaps were unavailable authenticated dogfood, unconfigured production providers, and a local model response that completed after 32,524.8 ms but failed JSON parsing.

R17.2.2 changes only AI response/runtime operationalization and its UI status. It does not redesign the three R17.2.1 contracts, add Impact Intelligence, or add a domain write/database.

## 2. Fast-Track Acceptance Policy

This phase uses `implement → test → build → deploy → best available validation → accept with operational gaps`. Missing production login and provider configuration are tracked as operations work, not repeated product closure phases. Only security, data corruption, authority/customer-acceptance integrity, or core workflow failure would block acceptance; none was found.

Accepted evidence consists of complete code, full affected tests, production build, successful CI, exact component deployments, fail-closed production authorization, deterministic fallback, safe provider status, and a successful bounded local JSON-mode probe.

## 3. AI Runtime Adapter

`ReviewerAIProvider.generate_grounded_review(...)` is the small provider-independent boundary. It receives the selected provider capability record and invokes the existing Document Again provider abstraction with common model, prompt, token, JSON-mode, connect-timeout, and read-budget inputs.

Safe provider capabilities now distinguish `supports_structured_output`, `supports_json_mode`, and `supports_streaming`. Reviewer business logic does not know provider URLs, credentials, response envelopes, or authentication styles.

Internal outcomes are no longer collapsed:

```text
AVAILABLE
NOT_CONFIGURED
UNAVAILABLE
TIMEOUT
RATE_LIMITED
MALFORMED
INVALID_CITATION
UNSUPPORTED_CLAIM
DISABLED
```

The UI-level operational states are `AI_AVAILABLE`, `AI_NOT_CONFIGURED`, `AI_UNAVAILABLE`, and `AI_DEGRADED`. The safe `/reviewer-ai/status` endpoint returns only status, concise message, selected provider/model identifiers when available, prompt version, and non-secret capabilities. It requires normal authentication.

## 4. Structured Output Recovery

Providers with JSON capability receive their native constraint:

- Ollama: `format=json` plus bounded `num_predict`.
- OpenAI-compatible providers: `response_format={type: json_object}`.
- Gemini: `responseMimeType=application/json`.

The response pipeline is deterministic and ordered:

1. Native JSON parse.
2. Balanced JSON-object extraction from a fence or leading/trailing prose.
3. Safe trailing-comma removal only.
4. Required-array schema and maximum-size validation.
5. Citation, support, classification, history, numeric/version/change, and authority validation.
6. Fail closed to deterministic review.

It does not convert arbitrary prose into claims, infer missing citations, close truncated objects, or repair missing fields. Parser metadata records `NATIVE_JSON`, `EXTRACTED_JSON`, or `SAFE_TRAILING_COMMA_REPAIR`.

The former 32.5-second event is classified `MALFORMED_RESPONSE`, not a timeout: local generation completed and then raised `JSONDecodeError`. With Ollama JSON mode enabled, a bounded live local compatibility probe returned the complete required schema as valid JSON in 12,545.3 ms.

## 5. Grounding & Citations

Every factual focus, risk/exception, reviewer question premise, and reading recommendation still requires known evidence IDs. Missing/unknown IDs remove the item. Lexical support is supplemented with category guards:

- every numeric/duration claim must appear directly in cited evidence;
- version/revision claims require document/revision evidence;
- added/removed/modified/changed claims require an explicit change/comparison item;
- approved/waived/authorized/signed/accepted claims require governance or acceptance evidence;
- CUSTOMER/FORMAL_EXTERNAL acceptance still requires explicit authoritative classification and decision;
- `NOT_RECORDED` cannot support unchanged/no-change certainty;
- approval, rejection, signing, acceptance, and go-live recommendations are rejected.

Responsibility context now also has a backward-compatible deterministic `RESPONSIBILITY` evidence item with role, purpose, confirms, excludes, gate, and policy provenance. This makes “why it matters to your role” citeable rather than prompt-only.

Provider free-form summary/limitations remain outside the trusted factual display channel. The visible summary is a deterministic count of validated cited items. Citation drill-down continues to resolve only IDs in the current packet and shows source, change, values, classification, and provenance.

## 6. Reviewer Quality

Prompt `reviewer_ai_prompt/v2` asks for five concise outcomes: material change, reviewer focus, role significance, unresolved items, and questions before deciding. The structured output now supports:

```text
focus_items: title + explanation + evidence_ids
risks_and_exceptions: title + explanation + evidence_ids
reviewer_questions: question + evidence_ids
suggested_reading: section + reason + evidence_ids
limitations
```

The UI renders concise titles and explanations. Technical/business prioritization uses existing reviewer context and its citeable policy evidence; it does not invent permission or downstream impact. Suggested reading and questions must cite the changed/source/responsibility evidence that justifies them.

## 7. Failure / Disabled / Cache / Stale

Default reviewer-specific budgets are 5 seconds to connect, 30 seconds for a remote provider response, and 40 seconds for local generation. They are environment-configurable, apply only to reviewer AI, and replace the Council’s longer general-purpose defaults for this path. There is no automatic retry and therefore no retry accumulation. A user may manually retry only after failure; refresh after success remains explicit.

Evidence and deterministic brief load independently on document open. AI starts only after `Show AI guidance`; it cannot block document viewing, evidence, review, approval, or sign-off. Failure returns the precise internal outcome with a concise non-secret UI message and leaves deterministic review ready.

Cache identity remains packet hash + reviewer context + prompt version + provider/model. `force=true` is the explicit manual refresh/retry bypass. Packet changes invalidate the cache identity, and the frontend independently refuses to display guidance whose evidence hash is stale. Cache is bounded to process memory; no database was introduced.

Audit metadata includes result/operational status, recovery method, provider/model, prompt and brief versions, packet hash, generated time, citation IDs, cache identity/hit, input/output byte sizes, and latency. No secret or chain-of-thought is stored. Optional Helpful/Not helpful feedback is deferred because it would introduce persistence/analytics outside this bounded phase.

## 8. UX

The existing deterministic Reviewer Change Brief remains first and primary. The AI area now shows a safe readiness badge/message (`AVAILABLE`, `NOT CONFIGURED`, `UNAVAILABLE`, or `DEGRADED`), advisory/human-decision labels, loading state, validated structured content, stale warning, and evidence links.

`Retry AI guidance` appears only after failure; it is disabled during the call. Successful guidance retains explicit Refresh and Hide. React lifecycle does not trigger AI because the call occurs only from the user event handler. Operational status and evidence reads are independent and inexpensive; no model call occurs during normal page load.

Authenticated production dogfood remains `OPERATIONAL_BACKLOG` under the fast-track policy. Production shell/build/health/status/auth boundary are validated without pretending protected reviewer UI was exercised.

## 9. Tests

Document Again: **159 passed**. Focused reviewer: **23 passed**. OIDA frontend: **7 passed**. Gateway: **3 passed**. Lint passed with the accepted pre-existing warnings; production build passed with the accepted existing bundle-size warning.

Parser coverage includes native JSON, markdown fences, leading/trailing text, safe trailing comma repair, arbitrary malformed text, truncation, missing fields, missing citations, and unknown IDs.

Safety coverage includes unsupported facts, fake numeric schedule delay, fake CUSTOMER acceptance, TEST-to-CUSTOMER promotion, unknown history, prompt injection, authorization/fail-closed routes, approval recommendation, version/change/category checks, and role evidence.

Operational coverage includes available mocked provider, not configured, timeout, malformed response, disabled, failure fallback, cache miss/hit, stale identity, manual retry/force bypass, JSON-mode/budget forwarding, status states, and local native JSON compatibility. Frontend tests distinguish loading, idle, failure, ready, stale, valid/invalid citations, and retry eligibility.

GitHub CI run `32563527594` for `2699496` completed successfully.

## 10. Deployment

Only changed components were deployed:

- Document Again Fly release 22, image `deployment-01M0MAW86QCS10FHDSYRG6AF6S`, machine `185de20c125718`, one passing check.
- OIDA Web Cloudflare Pages deployment `c423cb04-80b8-4619-85f7-c40d4dd44f7b`, production branch `main`, source `2699496`.

Production custom domain returned HTTP 200 and served `index-DbvmAFsn.js`. Document Again `/api/health` returned HTTP 200. Anonymous AI status returned HTTP 401, preserving fail-closed authorization. Safe status evaluated inside the deployed runtime returned:

```text
status=AI_NOT_CONFIGURED
message=AI is not configured. Deterministic review is ready.
prompt_version=reviewer_ai_prompt/v2
provider=null
model=null
```

No production credential was added. Exact deployment and source proofs pass.

## 11. Security / Governance

The provider adapter inherits the authorized, minimized Reviewer Evidence projection. Credential-shaped fields remain stripped; provider status exposes no key, URL secret, cookie, token, hidden prompt, or configuration value. Production status and reviewer APIs require existing actor authentication. `SECRET_EXPOSURE=0`.

Schema recovery never weakens citation/support validation. AI cannot mutate truth, severity, acceptance classification, governance, risks, defects, CRs, milestones, waivers, approvals, acceptance, or sign-off. TEST/INTERNAL evidence cannot become CUSTOMER/FORMAL_EXTERNAL. Human decision controls are unchanged and manual. New domain writes: zero. New database: no. Impact Intelligence: deferred.

Security, governance, deterministic workflow, and customer-acceptance integrity pass. No blocking condition was found.

## 12. Operational Backlog

- **OPS-AI-01 — Configure authorized production AI provider.** Owner: operations/security. Supply provider/model through the existing protected configuration mechanism; never commit or paste credentials.
- **OPS-AI-02 — Production AI smoke test.** After OPS-AI-01, run one bounded reviewer request and verify structured output, citation resolution, latency/status, and cache without creating acceptance evidence.
- **OPS-AUTH-01 — Authenticated reviewer dogfood.** Complete normal Account Again login and inspect deterministic-first rendering, status/success/failure, citation drill-down, network/console, and manual controls.
- **OPS-AI-03 — Local model compatibility verification.** Partially complete: native JSON schema probe passed in 12,545.3 ms. Repeat with a representative authorized Reviewer Evidence packet and record quality/rejection rate.

These are operations tasks, not new product phases and not blockers to R17.2.2 acceptance.

## 13. Acceptance

R17.2.2 is **ACCEPTED_WITH_OPERATIONAL_GAPS**. The runtime adapter, native structured modes, safe recovery, precise outcomes, bounded failure behavior, role-grounded quality schema, strengthened category/authority validation, operational status, retry/cache/stale behavior, tests, CI, build, security/governance, and exact deployments pass.

Production AI remains `AI_NOT_CONFIGURED`, and authenticated dogfood remains unavailable; both are explicitly permitted operational backlog under this phase’s fast-track policy. Deterministic review remains ready, and production access remains fail closed. No repeated closure phase is recommended.

```text
OIDA R17.2.2 — AI REVIEWER FAST-TRACK FINAL REPORT

BASELINE_HEAD=4d4d160b51aa7d90170ef19e9ac5be6c12e7f9b2
IMPLEMENTATION_COMMIT=26994961eace56a94d2ea4699235577f08398e83
FINAL_HEAD=THIS_ARTIFACT_COMMIT_SEE_REPOSITORY_HISTORY_AND_FINAL_HANDOFF

SOURCE_CODE_CHANGED=YES
WORKTREE_FINAL=CLEAN_AFTER_FINAL_COMMIT
CI=PASS_RUN_32563527594

AI_RUNTIME_ADAPTER=PASS_ReviewerAIProvider
STRUCTURED_OUTPUT=PASS_NATIVE_JSON_MODE_WHERE_SUPPORTED
JSON_RECOVERY=PASS_NATIVE_EXTRACTED_SAFE_TRAILING_COMMA
MALFORMED_RESPONSE_HANDLING=PASS_FAIL_CLOSED_PREVIOUS_FAILURE_CLASSIFIED

AI_PROVIDER_ABSTRACTION=PASS_EXISTING_PROVIDER_BOUNDARY_EXTENDED
AI_PROVIDER_RUNTIME=AI_NOT_CONFIGURED_PRODUCTION
AI_OPERATIONAL_STATUS=PASS

DETERMINISTIC_BRIEF=PASS_INDEPENDENT
NON_BLOCKING_AI_UX=PASS_EXPLICIT_ASYNC_USER_ACTION

AI_REVIEWER_QUALITY=PASS_CONCISE_FIVE_NEEDS_SCHEMA
ROLE_AWARE_GUIDANCE=PASS_CITEABLE_RESPONSIBILITY_EVIDENCE
REVIEWER_QUESTIONS=PASS_STRUCTURED_GROUNDED
SUGGESTED_READING=PASS_STRUCTURED_GROUNDED

AI_CITATIONS=PASS
CITATION_VALIDATION=PASS
CITATION_DRILLDOWN=PASS_IMPLEMENTED_AUTH_DOGFOOD_BACKLOG

UNSUPPORTED_CLAIM_PROTECTION=PASS
CUSTOMER_ACCEPTANCE_PROTECTION=PASS
UNKNOWN_HISTORY_PROTECTION=PASS
PROMPT_INJECTION_DEFENSE=PASS
AI_AUTHORITY_BOUNDARY=PASS

AI_DISABLED=PASS
AI_FAILURE_FALLBACK=PASS
AI_RETRY=PASS_MANUAL_ONLY_NO_AUTOMATIC_RETRY
AI_CACHE=PASS
STALE_AI_GUIDANCE=PASS

AI_AUDIT_METADATA=PASS

AI_LATENCY=12545.3_MS_LOCAL_NATIVE_JSON_COMPATIBILITY_PROBE
AI_FAILURE_DETECTION_LATENCY=MAX_5S_CONNECT_30S_REMOTE_40S_LOCAL_RESPONSE_BUDGET
DETERMINISTIC_BRIEF_LATENCY=0.02_MS_ACCEPTED_SAMPLE

NEW_WRITE_ACTIONS=0
NEW_DATABASE=NO
IMPACT_INTELLIGENCE=DEFERRED

DOCUMENT_TESTS=PASS_159
REVIEWER_TESTS=PASS_23
AI_RUNTIME_TESTS=PASS
AI_SECURITY_TESTS=PASS
FRONTEND_TESTS=PASS_7
GATEWAY_TESTS=PASS_3
LINT=PASS_WITH_PRE_EXISTING_WARNINGS
BUILD=PASS

DEPLOYMENT=PASS_DOCUMENT_RELEASE_22_AND_PAGES_c423cb04
PRODUCTION_REVISION_PROOF=PASS_SOURCE_2699496_BUNDLE_index-DbvmAFsn.js

SECURITY_REGRESSION=PASS
GOVERNANCE_REGRESSION=PASS
CUSTOMER_ACCEPTANCE_INTEGRITY=PASS

AUTHENTICATED_DOGFOOD=OPERATIONAL_BACKLOG_OPS-AUTH-01
PRODUCTION_AI_PROVIDER=OPERATIONAL_BACKLOG_OPS-AI-01

OPERATIONAL_BACKLOG:
- OPS-AI-01 Configure authorized production AI provider.
- OPS-AI-02 Run production AI smoke test.
- OPS-AUTH-01 Complete authenticated reviewer dogfood.
- OPS-AI-03 Repeat local compatibility with representative authorized evidence.

R17_2_2=ACCEPTED_WITH_OPERATIONAL_GAPS

NEXT_STEP=Move to Cross-Service Impact Intelligence Foundation; do not run another R17.2.2 closure phase.
```
