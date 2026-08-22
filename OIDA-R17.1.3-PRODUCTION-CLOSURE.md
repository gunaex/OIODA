# OIDA R17.1.3-V — Authenticated Production Closure

Date: 2026-08-22 (Asia/Bangkok)  
Start head: `45f70c73e032e3fb20e847652f657e95bd19778b`  
Final source commit: `667cbdb31c98d7a27107af12ffda55b4ee80f8f5`

## 1. Baseline

The pass began on clean `main` at the accepted R17.1.3 artifact commit. Implementation commit `323d37271786d522d9d8d522f51accfaefc80c2c`, Document machine version 20, Pages deployment `1f73ab5f-fc9b-431d-a300-bdf6d180f2f6`, and their CI evidence were intact. No capability phase was started.

## 2. Production Revision

Initial production served the accepted `index-BkWud19Q.js` and `index-DIk2aTON.css`. Authenticated network validation found duplicate project loads, so three minimal frontend lifecycle fixes were made:

| Commit | Defect | Cause | Minimal fix |
|---|---|---|---|
| `5dac990` | Project truth batch repeated as PM/QA context resolved | ProjectHome effect depended on values it did not read | key batch only by Document project ID |
| `9e7dc18` | production effect replay | development StrictMode wrapped the production tree | retain StrictMode only in development |
| `667cbdb` | project shell remounted after service enrichment | Account auth completed before PM/QA/Conductor probe | settle the existing probe before mounting protected content |

Final Pages deployment is `ec0fa909-56d1-467c-a518-5daecf8c8a71`, source `667cbdb`, serving `index-Bne1Xpf9.js` and `index-DIk2aTON.css`. Document Again remains unchanged and healthy on Fly machine version 20, image `deployment-01M0KY8SAW1YCMP4NKNYYSWPD6`. No redeploy of Document or owner services was necessary.

## 3. Account Authentication

A fresh normal Account Again login was completed by the human in the production OIDA flow. `/api/auth/me` returned HTTP 200, identity resolved, and the representative project was accessible. The same signed ecosystem identity was accepted through the gateway by Document Again, PM Again, QA Again, and Conductor Again without unexpected 401 or 403 responses. No password, token, cookie, or session ID was printed or committed.

## 4. Project Bindings

Authenticated `project_bindings/v1` returned HTTP 200 for `prj_853bcc5700a54c8db170`:

- PM: one explicit `BOUND` project.
- QA: five explicit `BOUND` and distinct scopes.
- Infra: explicit `UNBOUND`, with no external design ID.

No binding was inferred from a display name and no synthetic owner data was created.

## 5. Project Truth

Authenticated `project_truth/v1` returned HTTP 200. PM and QA source status were `OK`; Infra was `UNBOUND`; overall freshness was `UNKNOWN` because current owner responses do not expose usable update timestamps. PM and QA provenance was present. Partial state was true solely because Infra was honestly unbound. The returned server duration was 160.9 ms in the first closure sample.

## 6. Project Attention

The same response embedded `project_attention/v1`; there is no parallel truth request or duplicate attention endpoint. Actual counts were:

```text
blockers   = 0
issues     = 0
unverified = 1
```

The only attention item was `INFRA / UNVERIFIED / SOURCE_UNBOUND`. Unbound was not converted to zero, resolved, pass, or ready. Delivery Health is a source-linked deterministic projection and is not go-live authorization or customer acceptance.

## 7. PM Validation

All four direct PM owner calls returned HTTP 200: dashboard, Gantt, effort-estimate summary, and effort-budget gauge.

| Capability | PM owner fact | `project_truth/v1` | Attention/UI result |
|---|---|---|---|
| Next milestone | zero Gantt rows/milestones | milestone count 0; next milestone null | `—` / authoritative empty |
| Slippage | no incomplete dated items | slipping count 0 | `0 overdue` |
| Blocked dependencies | empty authoritative Gantt | blocked count 0 | `0` |
| Effort variance | status null; contracted total missing | remaining/status null with missing config | `UNKNOWN`, not money |

Unfinished work was not classified as late without an elapsed date.

## 8. QA Validation

Five distinct explicit QA scopes were queried independently. All five dashboard, five suites, and five defects requests returned HTTP 200. The aggregate contained zero test cases, zero suites, and zero defects; there were therefore no entity IDs to overlap or deduplicate.

Normalized truth remained source `OK`, test definitions `EMPTY`, readiness/execution/evidence `NOT_STARTED`, and remaining/failed/blocked/blocking-defect counts at authoritative zero. Evidence classification remained intentionally partial: TEST `NOT_PRESENT`, INTERNAL `UNKNOWN`, CUSTOMER `NOT_PROVIDED_BY_QA`. TEST, INTERNAL, and CUSTOMER were never equated.

## 9. Infra Validation

Infra was explicitly unbound and generated zero owner calls. Architecture revision, feasibility, environment, connectivity, implementation, and preflight were displayed as `UNBOUND`/unverified rather than zero or ready. Environment readiness remains partial because owner environment records lack scoped readiness. Implementation and preflight remain partial because no explicit implementation-plan or execution-package binding exists. No design URL was fabricated.

## 10. Overview Validation

Authenticated production Overview visibly rendered Delivery Workspace, Project Attention, PM Attention, QA Readiness, Infra Readiness, and collapsed cross-service truth. The visible 0/0/1 attention totals and PM/QA/Infra fields matched the API. Sparse data looked intentional on desktop. At a 390×844 viewport the attention sections remained present, stacked, and produced no horizontal document overflow; the pre-existing fixed sidebar leaves the content column cramped and is recorded as a shell-level future UX gap, not changed in this closure.

## 11. Owner Link Validation

- PM route format is known and contains no credential, but a clean standalone navigation showed the PM sign-in flow. Auth continuity is not proven; link remains unavailable.
- QA has five valid scopes, no unambiguous single target, and standalone navigation showed the QA sign-in flow. No selector was added; link remains unavailable.
- Infra is unbound and has no stable design route; owner link is not applicable/blocked.

OIDA’s internal planning, QA, and Infra drill-down links remain usable. No credential was passed in a URL.

## 12. Browser Network/Console

The final production capture used a clean Chrome profile with the fresh Account session applied through the normal OIDA storage contract. All observed application requests returned below HTTP 400; there were no unexpected 401, 403, 404, 500, or CORS failures. The final trace proved one logical authenticated truth GET and one normal OPTIONS preflight with distinct request IDs. PM/QA context calls were bound; no Infra invalid-pointer request occurred. Console events: 0. JavaScript exceptions: 0.

## 13. Performance

Five fresh authenticated truth/attention samples were 281.272, 288.760, 291.711, 312.648, and 313.770 ms. Median was 291.711 ms, better than the prior R17.1.2 truth baseline of approximately 316.882 ms and without meaningful regression. Project Attention uses the same response and therefore has the same latency. Final Overview reached visible Project Attention in 2.110 seconds in the clean uncached browser capture.

Downstream owner calls were exactly PM 4 + QA 15 + Infra 0 = 19. There were no retries, duplicate scope IDs, or owner N+1 calls beyond the accepted QA 5×3 aggregation.

## 14. Precheck Regression

Authenticated HD-MIG-01 precheck returned HTTP 200 in 370.601 ms. It remained `NOT_READY`, with 0 ready, 14 missing, 0 no-source, and 0 unknown modules, and embedded `project_truth/v1`. The extended truth contract caused no precheck regression.

## 15. Security/Governance

Security scan found no committed credential or owner secret. No auth bypass, token-in-URL, new permission, owner write, database, or AI feature was added. The closure performed only read requests plus the explicitly requested derived precheck refresh. Flexible governance, waivers, Proceed With Risk, Not Applicable, version-specific evidence, and signed revision immutability were not changed. Delivery Health and QA state do not imply customer acceptance.

## 16. Known Partial Capabilities

- QA evidence classification: TEST is authoritative; INTERNAL and CUSTOMER are not supplied by QA.
- Infra environment readiness: owner environments lack scoped readiness state.
- Infra implementation readiness: no explicit implementation-plan binding.
- Infra preflight: no explicit execution-package binding.
- Go-live readiness remains deferred.
- Standalone owner auth continuity is unproven; QA additionally needs a scope choice and Infra needs a stable bound route.
- The pre-existing fixed navigation shell is cramped at phone width, although the attention content stacks without document overflow.

## 17. Final Acceptance

R17.1.3 Wave 1 is accepted. Production revisions, fresh authentication, ecosystem identity, bindings, truth, attention, owner facts, sparse semantics, Overview UI, network, console, latency, call budget, and precheck are proven. Approved partial and deferred capabilities remain honestly partial/deferred and do not invalidate the implemented slice.

```text
R17_1_3_IMPLEMENTATION=ACCEPTED
R17_1_3_PRODUCTION=ACCEPTED
R17_1_3_BROWSER=ACCEPTED
R17_1_3=ACCEPTED
```
