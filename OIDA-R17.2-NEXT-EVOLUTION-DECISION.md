# OIDA R17.2 — Next Evolution Decision

Date: 2026-08-22 (Asia/Bangkok)

Baseline: `9824ab355a34f274efae738ec79daf143de67ff5`

Scorecard: `OIDA-R17.2-OPTION-SCORECARD.csv`

Decision: `RECOMMEND_HYBRID`

Decision principles applied throughout: truth before intelligence; deterministic before AI; AI advises and humans decide; projection is not authority; completeness is not an end in itself; optimize for human decision quality; build the smallest slice with clear value.

## 1. Current Product Baseline

R17 through R17.1.3 are accepted. OIDA now provides document governance, exact-version acceptance evidence, flexible governance, owner-derived `project_truth/v1`, live Document Precheck, Project Attention, Delivery Health, PM/QA/Infra projections, and authenticated production/browser proof.

The production baseline is useful but sparse: PM is bound and authoritative with an empty representative Gantt and unconfigured effort; QA has five bound scopes whose owner calls succeed but whose representative data is empty/`NOT_STARTED`; Infra is explicitly `UNBOUND`. Attention is therefore honest—0 blockers, 0 issues, 1 unverified—and the truth endpoint median was 291.711 ms across five authenticated samples with 19 downstream calls. OIDA reports status and provenance correctly; it does not yet routinely explain the meaning of a document revision to the person asked to act.

Current maturity: **governed, cross-service, read-oriented project truth with human-controlled acceptance; ready for bounded decision assistance, but not for an authoritative cross-service intelligence graph.**

Evidence reviewed:

- `OIDA-INTEGRATION-AUDIT.md` and `.csv`
- `OIDA-R17.1.2-CROSS-SERVICE-TRUTH.md` and `OIDA-R17.1.2-FULL-CLOSURE.md`
- `OIDA-R17.1.3-CAPABILITY-DECISION.md` and matrix
- `OIDA-R17.1.3-PROJECT-ATTENTION.md` and `OIDA-R17.1.3-PRODUCTION-CLOSURE.md`
- Current Document Again models/services, deliverable governance, trace/impact services, and OIDA delivery UX

## 2. Current User Friction

A project user can see health, attention, readiness, provenance, document lifecycle, version history, sign-off history, source snapshot/hash, and deterministic role responsibility. The existing sign-off panel already answers “why am I being asked?”, “what am I confirming?”, and “what am I not confirming?” from gate policy.

The remaining manual work is concentrated in interpretation:

- A reviewer must open and compare versions or source snapshots to discover material changes.
- Version history shows that versions exist, but not a consolidated evidence-backed change set.
- Risks, known exceptions, governance state, and changed source truth sit in separate fields/views.
- The user must decide which changes matter to their role and remember relationships across documents and specialist services.
- Project Attention says where attention is needed, but generally not how a specific change alters the decision now requested.
- Standalone PM/QA owner navigation needs another sign-in; QA also has five possible scopes. Infra has no binding/stable target. This limits drill-down continuity but does not invalidate OIDA truth.

The highest-frequency safe opportunity is therefore to reduce comparison and reading load at an existing human decision point.

## 3. Option A — Reviewer/Approver Intelligence

### Value and viable product shape

Option A is highly viable. It directly improves review, approval, acceptance, and sign-off without transferring authority. Its best first form is not a generic chatbot: it is a **Reviewer Change Brief** attached to one exact document version and its predecessor.

Current deterministic inputs already include document/version identity, immutable snapshots, snapshot/content hashes, revision/supersession links, lifecycle, freshness/material-change flags, governance policy, roles, sign-off purpose, evidence class, known exceptions, precheck/readiness, project truth, attention, and audit history. Artifact and requirement revisions also have immutable ancestry, while the service exposes structural revision diff and semantic diff capabilities.

### What can be stated deterministically now

| Question | Current readiness | Boundary |
|---|---|---|
| Previous/current version | STRONG | Use explicit supersession/revision history; never guess adjacency. |
| Structural/content differences | STRONG for revision snapshots; PARTIAL for every human workbook section | Diff frozen structured snapshots and expose unavailable sections honestly. |
| Changed source facts | STRONG when both `source_snapshot`s exist | Compare typed snapshot paths and retain old/new values and provenance. |
| Changed requirements | STRONG inside Document Again | Use requirement revision IDs/ancestry and controlled change records. |
| Changed decisions/assumptions | PARTIAL | Only when represented as typed semantic/snapshot fields; free-text interpretation is advisory. |
| Changed project truth | PARTIAL | Snapshots permit comparison, but owner freshness/revisions are uneven and representative PM/QA data is sparse. |
| Material meaning and focus | AI-suitable, not authoritative | AI may interpret only cited deterministic evidence. |

The existing role brief is a strong starting point, but it is policy-level and accepts a role string; it does not yet map each changed item to role-specific responsibility or verify the entered role against the acting user. Reviewer, approver, signatory, project owner, and customer representative must receive different focus/exclusion language.

### Candidate minimal proposal

**Inputs:** exact current instance ID/hash/snapshot; explicit predecessor ID/hash/snapshot; deterministic structured diff; gate and role policy; precheck/readiness; unresolved known exceptions; current sign-off purpose/evidence class; source provenance and freshness.

**Outputs:** exact scope of review; old/new version identities and hashes; categorized changed/unchanged/unavailable facts; material-change reasons; role-specific focus and exclusions; open risks/exceptions; stale/unknown warnings; evidence citations pointing to snapshot paths, revisions, or audit records.

**UX location:** the existing Deliverables detail/sign-off panel, before the decision controls, with progressive disclosure into the exact evidence. It should complement—not duplicate—the current responsibility brief.

**AI role:** a later, clearly labeled advisory summary/challenge generated only from the deterministic evidence pack. It may prioritize reading and identify questions; it may not create facts, change readiness, recommend an authoritative decision, or sign.

**Human control:** the user opens source evidence, chooses the decision, records exceptions, and signs the exact version. The brief is never itself acceptance evidence.

**Acceptance criteria:** exact-version binding; reproducible deterministic output; every changed fact traceable to old/new evidence; honest unavailable/stale states; distinct role/purpose/evidence-class wording; TEST never represented as INTERNAL/CUSTOMER; no AI required for the page to work; AI statements cited and labeled; no automatic approval/acceptance; audit of brief inputs/output/model where AI is later enabled.

Size: **MEDIUM**. Time to first user value: **FAST**.

## 4. Option B — Change/Impact Intelligence

Option B has the greatest long-term platform upside, but the current cross-service graph is not reliable enough for a broad implementation.

### Linkage inventory

| Relationship | Readiness | Evidence |
|---|---|---|
| Requirement ↔ Document/artifact/revision | STRONG | Stable semantic IDs, baselines, revision bindings, trace links, requirement changes. |
| Requirement/decision ↔ other Document semantic objects | STRONG/PARTIAL | Explicit `TraceLink` traversal and revision context exist; coverage depends on authored links. |
| Document ↔ governance gate/sign-off/acceptance evidence | STRONG | Required gate, exact version/hash, purpose, evidence class, exceptions, audit. |
| Document ↔ PM work/milestone | WEAK | Bindings and aggregate project truth exist; canonical entity-level relationship edges do not. |
| Document ↔ QA scope/test/defect/evidence | PARTIAL/WEAK | Explicit QA scopes and some handoff/correlation IDs exist; document-to-test/defect linkage is not normalized. |
| Document ↔ Infra design/component/environment | WEAK for this project | IDs/revisions exist in the owner domain, but the production project is unbound and has no project graph edges. |
| PM ↔ QA ↔ Infra dependency | MISSING/PARTIAL | Work-package/correlation handoffs exist in places; no shared authoritative relationship contract. |
| Owner entity ↔ acceptance condition | WEAK | Project-level readiness can inform precheck, but entity-level acceptance relationships are not canonical. |

### Dependency graph readiness

Document Again already provides a useful intra-domain graph: stable `SemanticObject`s, provenance-bearing `TraceLink`s, deterministic traversal, relation paths, severity rules, and separation of `SYSTEM-DERIVED`, `INFERRED`, and unknown impact. That is not yet an ecosystem graph. `project_truth/v1` normalizes summaries and attention, not stable entity nodes/edges. PM’s generic linked entity fields are owner-local, QA scopes are plural, and Infra is unbound. Graph coverage would therefore be unknown precisely where a cross-service result could look most authoritative.

### Change-event inventory

| Change source | Stable ID | Timestamp | Revision/version | Event/audit | Before/after | Readiness |
|---|---:|---:|---:|---:|---:|---|
| Document/artifact revision | Yes | Yes | Yes | Yes | Snapshot/diff | STRONG |
| Requirement revision/change | Yes | Yes | Yes | Yes | From/to revisions | STRONG |
| Decision/assumption | Conditional | Usually | Conditional | Partial | Partial | PARTIAL |
| PM schedule/milestone | Yes locally | Yes/partial | Partial | Partial | Not common | WEAK/PARTIAL |
| QA status/test/defect | Yes locally | Yes | Mixed | Evidence/events exist | Not common | PARTIAL |
| Infra design revision | Yes locally | Yes | Yes | Domain history | Mixed | PARTIAL, untestable here |
| Environment readiness | Yes locally | Mixed | Weak | Weak | No common state transition | WEAK |
| OIDA binding change | Project/binding IDs | Yes in project audit paths | Weak | Partial | Mixed | PARTIAL |

### Candidate minimal proposal

Do not build a full graph. After a common provenance contract exists, pilot one narrow chain: **confirmed requirement change → explicitly linked Document artifacts/revisions → existing explicit QA/Infra handoff targets, with PM/QA/Infra candidates otherwise labeled UNKNOWN or AI-SUGGESTED.** Inputs are the controlled requirement change, explicit trace edges, bound owner IDs, and current owner state. Output is a provenance-preserving impact candidate list grouped as `EXPLICIT`, `DETERMINISTIC`, `AI-SUGGESTED`, and `UNKNOWN`; humans confirm or reject suggestions. Acceptance requires zero promotion of suggestions to truth, full paths/citations, explicit coverage/unknown reporting, and production fixtures with non-empty links.

Size: **VERY_LARGE** for the general capability; a post-foundation pilot is **MEDIUM/LARGE**. Time to first trustworthy user value: **SLOW**.

## 5. Option C — Truth Maturity

Option C improves completeness and is valuable only where it unlocks decisions. The current partial states have different causes:

| Partial area | Actual cause | Material now? | Decision |
|---|---|---:|---|
| QA INTERNAL/CUSTOMER evidence | Bounded authority, not missing QA truth: QA owns TEST; Document Again owns broader governance/acceptance evidence | No | Do not duplicate into QA. Preserve classification boundary. |
| QA TEST evidence | Representative project has no test evidence yet | No architectural blocker | Keep authoritative `NOT_PRESENT`/`NOT_STARTED`. |
| Infra environment readiness | Owner environment records lack scoped readiness semantics | Not for unbound project | Add only with an actual bound use case and owner contract. |
| Infra implementation readiness | No explicit implementation-plan binding in project truth | Not for unbound project | Defer until a bound project needs it. |
| Infra preflight | No explicit execution-package binding | Not for unbound project | Defer until package identity is real. |
| Infra owner route | No bound design/stable target; standalone auth continuity unproven | UX limitation, not truth corruption | Contract-test when a real binding exists; do not fabricate route. |
| Cross-service relationship provenance | No common entity-edge contract | Material for future B | Implement only the minimal contract when B begins. |
| Cross-service change envelope | Heterogeneous owner revision/audit shapes | Material for future B | Define a narrow versioned envelope before B pilot. |

The smallest useful C slice is therefore **C-lite**, not a dashboard-completeness campaign: formalize the evidence/provenance envelope needed by the Reviewer Change Brief (exact source kind/ID/version/hash/retrieved time/freshness and deterministic/advisory classification). In parallel design, but do not yet force, canonical external entity references and change-event fields for the later B pilot.

Size: pure C **MEDIUM/LARGE**; recommended C-lite **SMALL**. Time to first value: pure C **MODERATE**, C-lite **FAST**.

## 6. Data Readiness

Option A has the best usable data now. Immutable revisions, snapshots, hashes, role/gate policy, exact-version sign-off, exceptions, readiness, and project truth are sufficient for an honest deterministic brief. The main data limitation is semantic categorization coverage and uneven owner freshness—not a blocker if the output exposes unknowns.

Option B has strong Document-domain data but weak cross-service edge and event coverage. Empty PM/QA representative data and unbound Infra make production validation especially poor. Building intelligence over those gaps would risk plausible but ungrounded impact claims.

Option C’s named gaps are real, but several are correct ownership or project-data conditions rather than missing functionality. Only provenance/event foundations materially unlock the next intelligence layers.

## 7. Architecture Readiness

### Option A dependency map

- **Already Available:** immutable revision/snapshot chains; hashes; structural and semantic diff services; role/gate policy; responsibility brief; exact-version sign-off; exceptions; precheck; project truth/attention; audit history; advisory AI/provider patterns.
- **Missing but Easy:** normalized change categories; evidence pointer schema; brief contract/version; role/purpose-specific presentation; honest unavailable markers.
- **Missing and Material:** deterministic human-deliverable snapshot diff assembly; verified actor-to-role context; prompt/input/output audit and citation validation for later AI.
- **Potential Blocker:** legacy/current snapshots lacking comparable typed sections. Mitigate with partial coverage, never inferred completeness.

### Option B dependency map

- **Already Available:** semantic object identity, explicit trace links, deterministic impact traversal, revision context, correlations/work-package IDs in selected handoffs, owner bindings and truth provenance.
- **Missing but Easy:** shared relationship classification vocabulary and display labels.
- **Missing and Material:** canonical cross-service entity reference, owner-emitted change envelope, explicit relationship ingestion, coverage metrics, graph authorization/filtering, non-empty production fixtures.
- **Potential Blocker:** absent relationships can be indistinguishable from no impact; heterogeneous IDs/events and unbound Infra prevent trustworthy broad results.

### Option C dependency map

- **Already Available:** honest partial/unbound semantics, source ownership, binding normalization, owner provenance, readiness projection framework.
- **Missing but Easy:** documented ownership matrix and common evidence pointer fields.
- **Missing and Material:** owner environment readiness semantics; plan/package bindings; stable routed/authenticated owner context; common external edge/event contracts.
- **Potential Blocker:** no real Infra binding/data to validate new Infra truth; filling fields without owner authority would only manufacture completeness.

## 8. AI/Safety Analysis

AI adds genuine value to A by summarizing a bounded evidence pack, identifying material themes, and posing reviewer questions. It adds value to B by suggesting non-explicit relationships, but that use has materially greater hallucination and false-authority risk because missing graph coverage is hard for a user to see.

Required evidence model for either option:

1. Deterministic truth and advisory output are separate objects and separate visual states.
2. Every AI claim points to one or more immutable evidence references (source service, entity/revision, snapshot path/hash, retrieval/freshness time).
3. Unsupported output is rejected or shown as an explicit question, never a fact.
4. AI output records evidence-pack hash, prompt/template version, provider/model, generation time, and actor/request context.
5. AI output is not persisted into owner truth, readiness, governance, acceptance, or sign-off state.
6. Human decisions remain explicit and exact-version bound.
7. For B, relationship states remain `EXPLICIT`, `DETERMINISTIC`, `AI-SUGGESTED`, or `UNKNOWN`; AI suggestions require human confirmation before becoming explicit links.
8. TEST, INTERNAL, CUSTOMER, and FORMAL_EXTERNAL evidence classes remain distinct.

Security must apply project authorization before evidence assembly, minimize content sent to a provider, prevent cross-project retrieval, redact secrets/credentials, and treat document text as untrusted prompt input. The deterministic A slice should ship and remain useful with AI disabled.

## 9. User Workload Analysis

| Option | Work removed | New burden introduced | Net assessment |
|---|---|---|---|
| A | Manual version comparison, scattered evidence gathering, deciding what to read first | Reviewing cited brief and resolving exceptions | Highest immediate reduction at a necessary human decision point. |
| B | Remembering dependencies and checking multiple services after change | Reviewing graph coverage and suggested relationships | Potentially high, but poor links create verification work and mistrust now. |
| C | Workarounds caused by unknown bindings/readiness | More owner configuration and data stewardship | Useful foundation; limited daily relief for the current unbound/sparse project. |

A best fits “system does administrative/document work; humans retain important decisions.” B could eventually do the same across delivery domains, after evidence maturity. C improves inputs but mostly does not remove current reviewer labor.

## 10. Product Differentiation

- **A:** Makes governed documents decision-ready rather than merely generated and controlled. It advances **AI-Ready, Human-Led** through better human judgment and has strong near-term differentiation.
- **B:** Could make OIDA an active project intelligence/orchestration layer and has the highest long-term differentiation. Premature delivery would undermine that identity by overstating relationships.
- **C:** Makes OIDA more complete and reliable. It is necessary platform hygiene in selected areas, but is less visible and less differentiating by itself.

## 11. Weighted Scorecard

Scale: 1 poor, 2 weak, 3 moderate, 4 strong, 5 excellent. For feasibility and safety, a higher score means **easier/safer**, not more effort/risk. The suggested weights are retained because the accepted baseline makes user value and workload reduction more important than maximizing architectural ambition.

| Dimension | Weight | A Reviewer Intelligence | B Impact Intelligence | C Truth Maturity |
|---|---:|---:|---:|---:|
| User Value | 20% | 5 | 5 | 3 |
| Workload Reduction | 15% | 5 | 4 | 2 |
| Decision Support | 15% | 5 | 5 | 3 |
| Data Readiness | 10% | 4 | 2 | 4 |
| Architecture Readiness | 10% | 4 | 2 | 4 |
| Truth Reliability | 10% | 4 | 2 | 5 |
| Implementation Feasibility | 10% | 4 | 2 | 3 |
| Risk/Governance Safety | 5% | 4 | 2 | 5 |
| Future Platform Value | 5% | 4 | 5 | 4 |
| **Weighted Total** | **100%** | **4.50** | **3.50** | **3.40** |

Score explanations:

- **A:** 5s for direct user/decision/workload value; 4s elsewhere because most evidence and controls exist, while typed diff coverage, role verification, and AI audit/citations still need work.
- **B:** 5s for user/decision/platform potential and 4 for eventual workload reduction; 2s for readiness, reliability, feasibility, and safety because cross-service links/events/coverage are incomplete.
- **C:** 5 for truth/safety and 4 for data/architecture/platform foundations; 3 or 2 for immediate user, decision, workload, and feasibility because several gaps need owner changes or real bindings and do not affect the present project.

The broader unweighted evaluation is consistent: A is strongest in daily/frequent value and differentiation with medium effort/UX complexity and controllable AI/governance risk; B is strongest in future differentiation but has very-large effort, high UX/architecture/AI risk, missing-binding dependency, and weak production testability; C has low AI/governance risk but moderate user value, owner dependency, and time to value.

## 12. Risks

Risk level: Low / Medium / High.

| Risk | A | B | C | Mitigation |
|---|---|---|---|---|
| AI hallucination | Medium | High | Low | Deterministic evidence first; citations; advisory labels; reject unsupported claims; AI optional. |
| False authority | Medium | High | Low | Never let AI alter truth, gates, acceptance, or sign-off; preserve relationship classes. |
| Stale truth | Medium | High | Medium | Display source revision/retrieval/freshness and unknowns; exact snapshot binding. |
| Missing links | Low/Medium | High | Medium | A scopes to evidence present; B reports graph coverage and UNKNOWN, never “no impact” from absence. |
| User overload | Medium | High | Medium | Role-specific exception-first summary with progressive evidence; avoid graph/editor in first wave. |
| Architecture complexity | Medium | High | Medium/High | Versioned narrow contracts; no universal graph or owner-schema duplication. |
| Cross-service coupling | Low/Medium | High | Medium | Read-only adapters, canonical references, owner authority, asynchronous/event compatibility later. |
| Governance regression | Medium | High | Low | Exact-version binding, purpose/evidence-class separation, human decision, regression tests. |
| Security | Medium | High | Medium | Project authorization before retrieval; data minimization/redaction; provider controls; no token in URLs. |
| Performance | Medium | High | Medium | Reuse captured snapshots/truth; bounded evidence pack; cache by immutable hash; call budgets. |

## 13. Hybrid/Sequencing Analysis

`RECOMMEND_HYBRID` means one tightly bounded sequence, not simultaneous A+B+C:

1. **C-lite inside the A contract:** define immutable evidence pointers, deterministic/advisory classification, coverage/unknown semantics, and exact predecessor selection.
2. **A deterministic first:** build Reviewer Change Brief v1 from existing snapshots, diffs, governance, exceptions, and responsibility policy, with no AI dependency.
3. **A advisory second:** add a cited AI summary/challenger only after deterministic acceptance and audit controls pass.
4. **B foundation later:** standardize canonical external references, relationship provenance, and narrow change-event envelopes.
5. **B pilot later:** one explicit requirement-change chain; expand only from measured link coverage.
6. **C domain completion as demanded:** Infra readiness/bindings and owner-route continuity only against real bound projects and user decisions.

This hybrid scores like A for immediate product value while preventing an AI-shaped contract from becoming the source of truth. It does not authorize a cross-service graph or broad truth-completion program.

## 14. Recommendation

**RECOMMEND_HYBRID: C-lite evidence contract + Option A deterministic Reviewer Change Brief first; cited AI assistance second; Option B only after explicit relationship/event foundations.**

Why now: the product has already captured the evidence that humans otherwise gather manually, and the decision/sign-off UX already has the correct human authority boundary. Turning that existing evidence into a reproducible role-aware change brief provides immediate value without depending on populated PM/QA/Infra graphs.

Why not pure A first: a brief without a versioned evidence-pointer/coverage contract could blur deterministic facts and AI interpretation. C-lite is a prerequisite within the same small direction, not a separate maturity program.

Why not B first: cross-service entity relationships, common change events, before/after state, graph coverage, and representative production data are insufficient. Missing edges would create the highest false-confidence risk.

Why not C first: QA’s classification is intentionally bounded, Infra is unbound, and filling all partial fields would optimize dashboard completeness more than current user workload. Only C-lite items that unlock A/B should be prioritized.

## 15. Minimal Next Implementation Slice

**Reviewer Change Brief v1 — deterministic only**

- Select the explicit current human-deliverable instance and explicit predecessor; bind both IDs, versions, hashes, and snapshots.
- Produce a versioned evidence pack with typed changes, old/new values, source pointers, freshness, coverage, and unavailable sections.
- Combine the existing responsibility brief with sign-off purpose/evidence class to show role-specific “focus”, “confirm”, and “not confirming” boundaries.
- Surface material-change reasons, precheck/readiness changes, governance changes, unresolved risks, and known exceptions.
- Render the brief before sign-off controls with links/disclosure to exact evidence.
- Keep all decisions manual and bind any eventual decision to the exact current version as today.
- Record deterministic brief contract/version/hash for reproducibility; do not require a model provider.

First-slice acceptance requires deterministic repeatability, exact-version safety, honest partial/unknown coverage, role/purpose differentiation, no evidence-class collapse, no new owner writes, acceptable bounded latency, and regression proof that current governance/sign-off semantics are unchanged.

## 16. Explicit Non-Scope

### Do Not Build in the first implementation wave

- No autonomous review, approval, acceptance, sign-off, waiver, or Proceed With Risk.
- No AI-generated decision, opaque score, uncited “materiality” claim, or AI fact persisted as truth.
- No AI dependency in Reviewer Change Brief v1.
- No full cross-service graph, graph editor, universal ontology, or broad impact engine.
- No automatic creation/promotion of relationship links.
- No new universal hard gate or governance policy change.
- No duplication of QA/PM/Infra specialist registers or owner writes.
- No QA INTERNAL/CUSTOMER classification added merely for completeness.
- No fabricated Infra readiness, binding, owner route, or go-live meaning.
- No frontend/backend/gateway/database/deployment change in this R17.2 decision pass.

## 17. Future Sequence

1. Human approves this decision and the deterministic Reviewer Change Brief v1 boundary.
2. Implement and production-prove the deterministic brief against non-empty version changes and multiple roles/purposes.
3. Add optional cited AI summarizer/challenger with prompt/output/evidence audit; compare it against the deterministic pack and preserve a no-AI path.
4. Define canonical external entity references, relationship provenance, coverage semantics, and narrow change-event envelopes.
5. Seed and validate one non-empty requirement-change impact chain across explicit links; AI suggestions remain separate.
6. Expand Impact Intelligence only when measured link/event coverage supports each new relation type.
7. Complete Infra readiness/binding/route capabilities when real project bindings and owner semantics make them decision-relevant.

## 18. Human Approval Decision

The product owner should approve or reject one bounded direction: **C-lite evidence contract plus deterministic Reviewer Change Brief v1**. Approval does not approve AI, a cross-service graph, owner-domain completion, or any implementation beyond the minimal slice. Before implementation, confirm the exact evidence-pack contract, predecessor rules, role/purpose variants, acceptance fixtures, and non-scope above.

Executive summary: build an evidence-backed change brief at the existing review/sign-off point because OIDA already owns the necessary version, governance, and snapshot truth. Start deterministically, keep humans fully authoritative, and add cited AI only after the brief is reproducible. Do not start broad impact intelligence until cross-service links and change events are explicit and measurable; fill remaining truth gaps only when they unlock a real user decision.

```text
OIDA R17.2 — NEXT EVOLUTION DECISION FINAL REPORT

BASELINE_HEAD=9824ab355a34f274efae738ec79daf143de67ff5
FINAL_HEAD=THIS_ARTIFACT_COMMIT_SEE_REPOSITORY_HISTORY_AND_FINAL_HANDOFF
SOURCE_CODE_CHANGED=NO

CURRENT_PRODUCT_MATURITY=GOVERNED_CROSS_SERVICE_TRUTH_READY_FOR_BOUNDED_HUMAN_DECISION_ASSISTANCE

OPTION_A:
USER_VALUE=EXCELLENT
DATA_READINESS=STRONG
ARCHITECTURE_READINESS=STRONG
RISK=MEDIUM_CONTROLLABLE
EFFORT=MEDIUM
WEIGHTED_SCORE=4.50/5.00

OPTION_B:
USER_VALUE=EXCELLENT_LONG_TERM
DATA_READINESS=WEAK
ARCHITECTURE_READINESS=WEAK
RISK=HIGH
EFFORT=VERY_LARGE
WEIGHTED_SCORE=3.50/5.00

OPTION_C:
USER_VALUE=MODERATE
DATA_READINESS=STRONG_FOR_SELECTED_GAPS
ARCHITECTURE_READINESS=STRONG_FRAMEWORK_OWNER_DEPENDENT
RISK=LOW
EFFORT=MEDIUM_TO_LARGE
WEIGHTED_SCORE=3.40/5.00

RECOMMENDATION=RECOMMEND_HYBRID
SEQUENCING=C_LITE_EVIDENCE_CONTRACT_THEN_A_DETERMINISTIC_THEN_A_ADVISORY_THEN_B_FOUNDATION_AND_PILOT

MINIMAL_NEXT_SLICE:
- Deterministic Reviewer Change Brief v1 bound to exact current and predecessor versions.
- Versioned evidence pointers, change categories, coverage, freshness, and unknown semantics.
- Role/purpose-specific focus, confirmation, exclusion, risk, and exception presentation.

WHY_NOW:
- Existing immutable snapshots, hashes, governance, sign-off, responsibility, and project truth can remove reviewer comparison work now.
- The current human-controlled decision point is already established and production-proven.

WHY_NOT_A_FIRST=PURE_A_WITHOUT_C_LITE_COULD_BLUR_DETERMINISTIC_AND_ADVISORY_EVIDENCE;_A_REMAINS_THE_CORE_FIRST_PRODUCT_SLICE
WHY_NOT_B_FIRST=CROSS_SERVICE_EDGES_EVENTS_COVERAGE_AND_NON_EMPTY_PRODUCTION_FIXTURES_ARE_NOT_READY
WHY_NOT_C_FIRST=MOST_CURRENT_PARTIALS_ARE_BOUNDED_AUTHORITY_OR_UNBOUND_DATA_AND_DO_NOT_OUTWEIGH_REVIEWER_VALUE

REQUIRED_PREREQUISITES:
- Exact predecessor and immutable evidence-pointer contract.
- Deterministic/advisory separation with explicit partial and unknown coverage.
- Verified role/purpose/evidence-class rules and reproducible acceptance fixtures.

DO_NOT_BUILD:
- Autonomous approval, acceptance, sign-off, waiver, or risk acceptance.
- AI dependency, opaque score, uncited fact, or AI output persisted as authority.
- Full impact graph, graph editor, specialist duplication, or fabricated truth completion.

FUTURE_SEQUENCE:
1. Production-prove deterministic Reviewer Change Brief v1.
2. Add optional cited and audited AI reviewer assistance.
3. Establish relationship/change-event foundations and pilot one explicit impact chain.

R17_2_DECISION_PASS=ACCEPTED

IMPLEMENTATION_STARTED=NO

NEXT_STEP:
Present the recommendation for human approval before implementation.
```
