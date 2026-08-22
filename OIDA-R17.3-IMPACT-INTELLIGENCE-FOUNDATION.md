# OIDA R17.3 — Impact Intelligence Foundation

## 1. Baseline

R17.2.2 remains `ACCEPTED_WITH_OPERATIONAL_GAPS` at baseline `fcd7c5385da14aa7bd0b4cacc69b3309f7c68f57`. Its provider/login backlog remains separate and was not reopened. R17.3 adds a read-only impact foundation with no database, mutation, autonomous action, or acceptance invalidation.

## 2. Decision-Lite Findings

Repository-backed stable identities exist for project, requirement and immutable requirement revision, controlled document and document version, version-specific sign-off, semantic object, and exact trace link. Document source snapshots preserve bounded owner facts and sometimes a source revision. Human deliverable history supplies recorded before/after version context. PM/QA/Infra project truth may be partial, unavailable, or unbound; names and shared project membership are therefore insufficient relationship evidence.

Data readiness: document/version ownership `SUPPORTED`; requirement-to-document source snapshot `SUPPORTED`; exact semantic trace links `SUPPORTED`; version-specific acceptance `SUPPORTED`; requirement revision freshness `PARTIAL` because older snapshots may omit revision numbers; live PM/QA/Infra owner links `PARTIAL/MISSING` by binding. The useful supported slice was implemented and missing coverage remains honest `UNKNOWN`.

## 3. Entity Model

Implemented nodes are `PROJECT`, `REQUIREMENT`, `REQUIREMENT_REVISION`, `DOCUMENT`, `DOCUMENT_VERSION`, `ACCEPTANCE_EVIDENCE`, and typed `SEMANTIC_OBJECT` targets already stored by Document Again. Identity uses row IDs, canonical requirement codes, document IDs, instance IDs, sign-off IDs, and semantic IDs only. Display names, fuzzy matches, substrings, and generated slugs never create known relationships.

## 4. Relationship Contract

`impact_relationships/v1` contains `relationship_id`, `project_id`, typed source/target IDs, `relationship_type`, `relationship_class`, `source_authority`, provenance, observed time, and status. Authoritative classes fail construction without stable IDs and provenance. Relationships are derived per authorized read; none are persisted.

| Source Type | Relationship | Target Type | Class | Authority | Implemented |
| ----------- | ------------ | ----------- | ----- | --------- | ----------- |
| DOCUMENT_VERSION | BELONGS_TO | DOCUMENT | DETERMINISTIC | Document Again structural rule | Yes |
| REQUIREMENT | DERIVED_FROM | DOCUMENT_VERSION | EXPLICIT | Document source snapshot | Yes |
| REQUIREMENT | IMPLEMENTS / VALIDATED_BY / REFERENCES / DESIGNED_BY / AFFECTS / GENERATED_FROM / CONFIRMED_BY / SUPERSEDES | typed semantic object | EXPLICIT | Exact Document Again trace record | Yes, when stored |
| ACCEPTANCE_EVIDENCE | ACCEPTS | DOCUMENT_VERSION | EXPLICIT | Version-specific sign-off | Yes |
| Any stable source | AFFECTS or proposed semantic | typed target | AI_SUGGESTED | AI advisory metadata | Validation boundary only |
| Document context | unresolved PM/QA/Infra relation | unknown | UNKNOWN | No reliable authority | Yes |

## 5. Relationship Classes

Authority order is `EXPLICIT → DETERMINISTIC → AI_SUGGESTED → UNKNOWN`. The UI renders Known, AI Suggested, and Unknown separately. `AI_SUGGESTED` requires cited evidence, reason, optional confidence, generation/provider/model/prompt metadata, and `UNCONFIRMED`; it cannot be promoted by this release. `UNKNOWN` is a first-class result.

## 6. Change Event Contract

`project_change/v1` normalizes stable entity identity, change type, recorded before/after or `NOT_RECORDED`, source service/revision, timestamp, optional actor, and provenance. This slice emits controlled-document `CREATED`/`VERSION_CHANGED` and requirement `VERSION_CHANGED` events without fabricating missing history.

## 7. Deterministic Impact Rules

`impact_candidates/v1` carries the full source change, stable target, relationship and class, conservative impact type, rationale, evidence IDs, status, and rule ID/version. Implemented rules are `R17.3-KNOWN-LINK`, `R17.3-SOURCE-REVISION-STALE`, and `R17.3-ACCEPTED-VERSION-AWARENESS`, all version `1.0`. Projection is one-hop, cycle-safe, and deduplicated by stable target while retaining multiple relationship reasons. No global score or invented severity exists.

| Change | Relationship | Target | Impact | Class | Evidence |
| ------ | ------------ | ------ | ------ | ----- | -------- |
| Requirement R1 updated | exact QA owner link `VERIFIES` | QA Scope Q1 | ATTENTION_REQUIRED | EXPLICIT | QA relationship record ID |
| Document version created | `BELONGS_TO` structural rule | controlled document | known context | DETERMINISTIC | instance/document IDs + rule version |
| Requirement source revision 4, current confirmed revision 5 | snapshot `DERIVED_FROM` requirement | document version | POTENTIALLY_STALE | EXPLICIT + deterministic rule | snapshot hash, relationship ID, revision ID |
| Document context has no stable PM link | none | PM | UNKNOWN | UNKNOWN | explicit missing-coverage rationale |
| Requirement may affect component | proposed AFFECTS | Infra component | possible impact only | AI_SUGGESTED | validated evidence IDs + AI metadata |

## 8. Stale Document Detection

When a document source snapshot records a requirement revision and current confirmed owner truth has a different revision, `R17.3-SOURCE-REVISION-STALE` emits `POTENTIALLY_STALE`. It does not say the document is wrong. If the snapshot has no revision, freshness remains unknown rather than inferred.

## 9. Acceptance Version Awareness

Qualifying `CUSTOMER`/`FORMAL_EXTERNAL` acceptance or sign-off is scoped to its exact document version. If the current version differs, the projection recommends evidence review, reports accepted and current versions, preserves historical acceptance, and explicitly says it does not automatically apply. It never labels customer acceptance invalid. `TEST`, `INTERNAL`, and non-acceptance purposes cannot qualify.

## 10. AI Suggested Relationships

AI runs only after known impacts and is optional. The new fail-closed validator rejects missing stable IDs/citations, unknown citations, and unsupported deterministic language such as schedule-delay, certain failure, mandatory rerun, or acceptance invalidation. Accepted proposals remain `AI_SUGGESTED/UNCONFIRMED`; confirmation/rejection writes are deferred. Existing R17.2.2 evidence hardening and prompt-injection treatment remain unchanged. Production provider configuration is not required for deterministic impact.

## 11. Impact UX

The Reviewer Change Brief now includes `Change Impact` before AI guidance. Known candidates show conservative type, rationale, relationship class, and rule provenance. Possible/AI Suggested is visibly advisory. Unknown lists uncovered PM/QA/Infra domains. Relationship provenance is drillable. The copy states that impact recommends review and triggers neither action nor acceptance invalidation. Existing evidence and review controls remain primary.

High-value stale and acceptance-version candidates also expose an actionable-only `project_attention/v1` contribution. Reviewer Brief carries `known_impacts`; reviewer evidence contracts were extended, not redesigned.

## 12. Authorization

The endpoint uses the existing authenticated actor and tenant/project guard. Relationships are resolved only from data already visible inside the authorized Document Again request. The pure projector provides a visibility predicate; denied targets and IDs are omitted entirely. Production anonymous requests return 401. Relationship aggregation does not broaden access, and credential-shaped fields are not introduced.

## 13. Tests

Document Again: **164 passed**; focused impact/reviewer: **28 passed**; OIDA frontend: **8 passed**; gateway: **3 passed**. Tests cover explicit and deterministic classes, unknown results, revision staleness, accepted older version, AI suggestion confinement, unsupported AI impact, stable-ID enforcement, provider-not-required behavior, permission filtering/no ID leak, partial coverage, duplicate path retention/deduplication, bounded cycle behavior, endpoint authorization path, and separated frontend sections. Existing reviewer tests retain prompt-injection, citation, provider failure, governance, and acceptance protections.

Lint passed with accepted pre-existing warnings. Production build passed with the accepted existing bundle-size warning.

## 14. Performance

Projection reuses the reviewer packet, source snapshot, local revision/sign-off records, and exact local trace registry. It performs zero new downstream calls. A 1,000-run pure one-hop projection probe measured p50 **0.010 ms**, p95 **0.010 ms**, max **0.090 ms** on the implementation host. Runtime responses expose relationship-resolution and impact-projection latency plus downstream-call count. Traversal depth is fixed at one.

## 15. Deployment

Implementation commit `d2acdba7867103e95c59d92f83abe2ebffe429ec` passed GitHub CI run `32564203020`. Document Again deployed as Fly release **23**, image `deployment-01M0MBRT55Z2G26KCB8H8S9NGN`, machine `185de20c125718`, with one passing health check and HTTP 200 `/api/health`. OIDA Web deployed through Cloudflare Pages as `ba499716` from the verified implementation SHA; the custom domain serves `index-C5FpP4PY.js` and `index-BCSLbyMd.css`.

Gateway health is available. Anonymous AI-status and impact requests both return HTTP 401. No gateway deployment was needed because its deny-by-default forwarding contract was unchanged.

## 16. Operational Backlog

- `OPS-AI-01` Configure an authorized production provider.
- `OPS-AI-02` Run the production AI smoke test.
- `OPS-AUTH-01` Run authenticated reviewer/impact browser dogfood.
- `OPS-AI-03` Run authorized-evidence provider compatibility.
- `OPS-IMPACT-01` Exercise production impact UX with an authenticated project containing revision and sign-off history.

These are environment/operator tasks, not new product phases.

## 17. Deferred Scope

- Human confirmation/rejection and promotion workflow for AI relationships.
- Impact action orchestration or automatic downstream writes.
- Full graph traversal, causal inference, and generic graph platform.
- Dedicated graph database or ontology editor.
- Additional owner-native PM/QA/Infra relationship adapters when stable authorized contracts exist.

## 18. Acceptance

```text
RELATIONSHIP_CONTRACT=PASS
CHANGE_EVENT_CONTRACT=PASS

STABLE_ENTITY_IDS=PASS
EXPLICIT_RELATIONSHIPS=PASS
DETERMINISTIC_RELATIONSHIPS=PASS
AI_SUGGESTED_RELATIONSHIPS=PASS
UNKNOWN_RELATIONSHIPS=PASS

IMPACT_CANDIDATES=PASS
DETERMINISTIC_IMPACT_RULES=PASS
STALE_DOCUMENT_DETECTION=PASS
ACCEPTED_VERSION_AWARENESS=PASS

AI_IMPACT_EXPLANATION=PARTIAL
AI_SUGGESTION_BOUNDARY=PASS
AI_CITATIONS=PASS
UNSUPPORTED_IMPACT_PROTECTION=PASS

PROJECT_ATTENTION_INTEGRATION=PASS
REVIEWER_BRIEF_INTEGRATION=PASS

PERMISSION_BOUNDARY=PASS
PARTIAL_SERVICE_BEHAVIOR=PASS
CYCLE_PROTECTION=PASS
DEDUPLICATION=PASS

NEW_WRITE_ACTIONS=PASS
NEW_DATABASE=PASS
AI_PROVIDER_RUNTIME=PARTIAL

UNIT_TESTS=PASS
INTEGRATION_TESTS=PASS
IMPACT_TESTS=PASS
AI_SAFETY_TESTS=PASS
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

`R17.3 = ACCEPTED_WITH_OPERATIONAL_GAPS`. Deterministic impact is complete and safely available without AI. Production AI and fresh authenticated dogfood remain operational gaps, as permitted by the fast-track acceptance policy.

---

## OIDA R17.3 — IMPACT INTELLIGENCE FOUNDATION FINAL REPORT

```text
BASELINE_HEAD=fcd7c5385da14aa7bd0b4cacc69b3309f7c68f57
IMPLEMENTATION_COMMIT=d2acdba7867103e95c59d92f83abe2ebffe429ec
FINAL_HEAD=ARTIFACT COMMIT (REPOSITORY HEAD; EXACT SHA REPORTED AT HANDOFF)

SOURCE_CODE_CHANGED=YES
WORKTREE_FINAL=CLEAN AND SYNCHRONIZED AT HANDOFF
CI=PASS (32564203020)

DECISION_LITE_RESULT=SUPPORTED NARROW CONTROLLED-DOCUMENT/REQUIREMENT/TRACE/ACCEPTANCE SLICE

ENTITY_TYPES_IMPLEMENTED=PROJECT, REQUIREMENT, REQUIREMENT_REVISION, DOCUMENT, DOCUMENT_VERSION, ACCEPTANCE_EVIDENCE, TYPED SEMANTIC_OBJECT
RELATIONSHIP_TYPES_IMPLEMENTED=BELONGS_TO, DERIVED_FROM, ACCEPTS, AND EXACT STORED TRACE TYPES

RELATIONSHIP_CONTRACT=impact_relationships/v1 PASS
CHANGE_EVENT_CONTRACT=project_change/v1 PASS

RELATIONSHIPS:
EXPLICIT=PASS
DETERMINISTIC=PASS
AI_SUGGESTED=PASS (VALIDATION/PROJECTION BOUNDARY)
UNKNOWN=PASS

IMPACT_CANDIDATES=impact_candidates/v1 PASS
DETERMINISTIC_IMPACT_RULES=PASS (3 RULES, VERSION 1.0)

STALE_DOCUMENT_DETECTION=PASS
ACCEPTED_VERSION_AWARENESS=PASS

AI_IMPACT_ASSISTANT=PARTIAL (SAFE BOUNDARY; PRODUCTION PROVIDER NOT CONFIGURED)
AI_PROVIDER_RUNTIME=AI_NOT_CONFIGURED / OPERATIONAL BACKLOG
AI_SUGGESTION_BOUNDARY=PASS; ALWAYS AI_SUGGESTED/UNCONFIRMED
AI_CITATIONS=PASS
UNSUPPORTED_IMPACT_PROTECTION=PASS

PROJECT_ATTENTION_INTEGRATION=PASS
REVIEWER_BRIEF_INTEGRATION=PASS

PERMISSION_BOUNDARY=PASS
PARTIAL_SERVICE_BEHAVIOR=PASS
DEDUPLICATION=PASS
CYCLE_PROTECTION=PASS
TRAVERSAL_DEPTH=1

RELATIONSHIP_RESOLUTION_LATENCY=p50 0.010 ms; p95 0.010 ms; max 0.090 ms pure probe
IMPACT_PROJECTION_LATENCY=INCLUDED IN RESPONSE METRICS
DOWNSTREAM_CALLS=0

NEW_WRITE_ACTIONS=0
NEW_DATABASE=NO
AUTONOMOUS_ACTIONS=0

DOCUMENT_TESTS=164 PASS
RELATIONSHIP_TESTS=PASS
IMPACT_TESTS=PASS
AI_SAFETY_TESTS=PASS
FRONTEND_TESTS=8 PASS
GATEWAY_TESTS=3 PASS
LINT=PASS WITH PRE-EXISTING WARNINGS
BUILD=PASS WITH EXISTING BUNDLE WARNING

DEPLOYMENT=PASS
PRODUCTION_REVISION_PROOF=FLY RELEASE 23 + PAGES ba499716 + SOURCE d2acdba
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

DEFERRED:
- Human relationship confirmation
- Impact action orchestration
- Full graph traversal
- Generic graph platform

R17_3=ACCEPTED_WITH_OPERATIONAL_GAPS
NEXT_STEP=MOVE ON; DO NOT CREATE AN R17.3 CLOSURE LOOP
```
