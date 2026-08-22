# OIDA R17.1.2-V2 — Production Closure

Date: 2026-08-22 (Asia/Bangkok)

## 1. Baseline

- Start HEAD: `0740aea40c49d7a86f9103e5266f9e06fa9261b8`
- R17.1.2 implementation: `89c550173325f265006503a62565ad3d16165987`
- Worktree at start: clean
- Application implementation was not redesigned.

## 2. Remaining Blockers From V1

V1 left frontend deployment, Account credentials, PM/QA normalized truth, an invalid Infra pointer, browser validation, CI, and Infra extended tests unresolved. V2 closed CI and Infra extended tests, established direct PM/QA owner evidence, and authoritatively classified the Infra pointer. Frontend deployment and Account-authenticated normalization remain blocked.

## 3. Cloudflare Deployment Recovery

Production is Cloudflare Pages. Wrangler has cached account metadata but no authenticated session, and no Cloudflare environment token is available. The installed Cloudflare GitHub App created a queued zero-run check suite for each push, no check run, and no deployment record. An authenticated GitHub API re-request returned 404. No alternative deployment model was introduced.

## 4. Frontend Revision Proof

Expected production build: `index-BGNniC9R.js`, `index-DY3WuLkC.css`.

Observed production: `index-Dgr_WjjG.js`, `index-BdiZJCCk.css`.

Result: `FAIL`. Production is independently proven to remain on the previous bundle.

## 5. PM Authentication

The intended integrated path uses the delegated Account Again ecosystem token. PM verifies that token, maps its email to a local user, and applies local authorization. An existing authorized local credential authenticated directly to PM, but it is not an Account ecosystem credential and cannot be forwarded through Document.

Direct PM owner reads all returned 200: dashboard 188.7 ms, Gantt 137.5 ms, effort summary 128.4 ms.

## 6. QA Authentication

QA uses the same delegated ecosystem identity architecture but its own local authorization and local JWT secret. The authorized local credential authenticated directly to QA. It cannot be combined with PM's distinct local session or substituted for the Account token.

All dashboard/suites/defects calls returned 200 for each of the five bound QA scopes.

## 7. Infra Binding Correction

The stored pointer returns 404. Authoritative `GET /api/v1/designs` returned `count=0`, proving there is no valid replacement design. The correct state is `UNBOUND`. Updating through the supported Document binding workflow requires the unavailable Account ecosystem session, so production remains unchanged. No name inference, direct database mutation, or fabricated design was used.

## 8. Project Bindings Runtime

- PM: bound and direct owner target valid
- QA: five explicit scopes, all direct owner targets valid
- Infra: stored pointer invalid; authoritative intended state is unbound

## 9. Authenticated Project Truth

`BLOCKED`. A valid Account ecosystem human session is required by gateway, Document, PM, and QA. Saved/local PM and QA sessions are service-specific and cannot safely satisfy that contract.

## 10. Owner ↔ Normalized Truth Comparison

| Domain | Owner Source | Owner Fact | OIDA Truth | Match | Provenance |
|---|---|---|---|---|---|
| PM | PM dashboard/Gantt/effort | green; schedule 0; milestones 0; dependencies 0; effort present | unavailable without Account token | BLOCKED | owner slug and direct retrieval timing recorded |
| QA | five QA dashboard/suites/defects scopes | all 200; tests/suites/open and blocking defects 0; evidence absent | unavailable without Account token | BLOCKED | five explicit scope IDs and direct retrieval timing recorded |
| Infra | design catalog / environments / readiness | design catalog empty; environments present; readiness empty | saved pointer remains INVALID | FAIL | owner design catalog and 404 pointer response |

QA's empty result is owner truth only. It is not customer acceptance and was not represented as such.

## 11. Provenance

Direct owner service, explicit entity/scope IDs, endpoints, and retrieval timings were recorded. Successful provenance through normalized production truth remains blocked because `project_truth/v1` could not be called with an ecosystem token.

## 12. Freshness

Direct reads were current runtime responses. Normalized FRESH/AGING state remains blocked. Deterministic stale/freshness contract tests continue to pass without modifying production timestamps.

## 13. Project Overview

Static inspection confirms Overview consumes `documentApi.projectTruth`. Runtime validation is blocked because the accepted frontend is not deployed and no Account session is available.

## 14. Document Precheck

V1 proved the deployed precheck embeds the same degraded truth snapshot. V2 could not run an authenticated all-owner precheck. The shared implementation and its focused tests pass.

## 15. Browser Validation

`BLOCKED_BY_ENVIRONMENT`. Chrome contains a saved OIDA login, but macOS Keychain did not grant noninteractive access and no current valid local-storage token exists. No OS credential boundary was bypassed. The stale frontend independently prevents acceptance.

## 16. Production Validation

`PARTIAL`. Service health, direct PM/QA owner reads, authoritative Infra absence, degraded truth integrity, CI, and Infra extended tests are proven. Frontend deployment and authenticated integrated truth are not.

## 17. Downstream Call Analysis

| Service | Endpoint / Operation | Calls per Snapshot | Parallel? | Needed? | Action |
|---|---|---:|---|---|---|
| PM | dashboard | 1 | service group parallel; internally sequential | yes | KEEP |
| PM | Gantt | 1 | service group parallel; internally sequential | yes | KEEP |
| PM | effort summary | 1 | service group parallel; internally sequential | yes | KEEP |
| QA | dashboard for five explicit scopes | 5 | service group parallel; scopes sequential | yes | KEEP pending batch API |
| QA | suites for five explicit scopes | 5 | service group parallel; scopes sequential | yes | KEEP pending batch API |
| QA | defects for five explicit scopes | 5 | service group parallel; scopes sequential | yes | KEEP pending batch API |
| Infra | design | 1 | service group parallel; internally sequential | yes when bound | KEEP |
| Infra | environments | 1 | service group parallel; internally sequential | yes when bound | KEEP |
| Infra | readiness | 1 | service group parallel; internally sequential | yes when bound | KEEP |

Total planned healthy calls: 21 = PM 3 + QA 15 + Infra 3. There are no duplicate scope IDs, retries, or repeated metadata calls. QA is an N×3 scope fan-out, not a duplicate-call bug. The practical minimum with current owner contracts is 21; a batch owner endpoint would be required to reduce it. No persistent cache was added.

## 18. CI / GitHub Actions

The zero-job failure was invalid YAML at the matrix working-directory flow mapping. Commit `be81e3c` repaired it. GitHub Actions run `32545835437` completed successfully.

## 19. Infra Extended Tests

The installed repo-documented fakecloud and OpenTofu tools were used. Full result: 361 passed, 8 skipped, one deprecation warning, in 469.39 seconds. The prior 18 environment failures are closed.

## 20. Security Regression

No credential was printed, committed, logged into an artifact, or copied between auth domains. No static token, fallback credential, unauthenticated endpoint, or broader service privilege was introduced.

## 21. Governance / Acceptance Integrity

Document 132/132, focused truth 12/12, PM 38/38, QA 101 passed / 5 skipped, and gateway 3/3 pass. No generation, transition, waiver, sign-off, customer acceptance, or fake evidence was created.

## 22. Remaining Blockers

- Restore an authorized Cloudflare deployment session or repair the existing Pages Git integration.
- Use an authorized Account Again human session to update the Infra binding to unbound and call integrated truth.
- Cross-check successful PM/QA normalized truth and provenance against the direct owner evidence.
- Deploy and prove the accepted frontend bundle, then validate Overview/precheck in a browser.

## 23. Final Acceptance

- Implementation: `ACCEPTED`
- Runtime: `PARTIAL`
- Production: `PARTIAL`
- Full R17.1.2 closure: `PARTIAL`

## V3 access-restoration addendum

The normal Cloudflare OAuth and OIDA Account Again login pages were opened during V3. Neither interactive authorization completed. Wrangler remained unauthenticated, no valid ecosystem session became available, production retained its old asset hashes, and the supported Infra binding workflow could not be invoked.

No V2 evidence was invalidated. The access boundary is now classified more precisely as `REQUIRES_USER_LOGIN`, and full closure remains `PARTIAL`.
