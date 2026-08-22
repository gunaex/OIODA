# OIDA R17.1.2-V — Runtime Closure

Date: 2026-08-22 (Asia/Bangkok)

## Revision and deployment

- Baseline: `a08438ae2b49a75924136820b3979f5f265e2d7e`
- Audit/recovery precursor: `8537a86`
- Dedicated R17.1.2 commit: `89c550173325f265006503a62565ad3d16165987`
- Document: Fly release 18, image `deployment-01M0KHJHVZ75R1TXEX0J8MTJZ9`, complete and healthy
- Gateway: Fly release 8, image `deployment-01M0KHJHVHKMQRRPP1SC1FHQX0`, complete and healthy
- Frontend: commit pushed to `origin/main`, but Cloudflare Pages continued serving the prior bundle; Wrangler had no authenticated session

The Fly images were built from the clean tested checkout at the R17.1.2 commit. The images do not expose a commit-SHA label, so the build/deploy transcript is procedural revision evidence rather than an independently queryable runtime SHA.

## Validation summary

| Check | Result |
|---|---|
| Worktree classification and secret scan | PASS |
| Document suite | 132 passed |
| Focused truth contract | 12 passed |
| Gateway | 3 passed |
| PM | 38 passed |
| QA | 101 passed, 5 skipped |
| Frontend lint/build | PASS; existing lint and chunk-size warnings |
| Infra | 343 passed, 8 skipped; 18 acceptance tests blocked by absent fakecloud/OpenTofu |
| Public health | OIDA, gateway, Document, PM, QA, Infra all HTTP 200 |
| Browser | BLOCKED_BY_ENVIRONMENT |

## Representative production project

Project `prj_853bcc5700a54c8db170` was inspected read-only. Its real stored pointers normalize to `project_bindings/v1` with a bound PM project, five bound QA scopes, and a bound Infra design.

Live `project_truth/v1` execution inside the deployed Document machine produced:

- PM: `UNAUTHORIZED`, HTTP 401
- QA: `UNAUTHORIZED`, HTTP 401
- Infra: `INVALID`, HTTP 404 for the stored design ID
- overall freshness: `UNKNOWN`
- partial: `true`
- duration: 288.9 ms
- downstream call count: 21

The response retained explicit status/error metadata and null domain truth. It did not translate authentication failure, invalid binding, or unavailable freshness into empty counts. Human deliverable precheck embedded the same contract version, generation timestamp, sources, and warnings, establishing the shared truth layer at runtime.

## Integrity and path review

Project Overview has one bounded-summary read: `documentApi.projectTruth`. Direct PM/QA reads that remain are limited to project identity/navigation and explicit binding-candidate selection. Document detail, precheck, and generation all call `build_project_truth`; no alternate precheck truth path was found.

Runtime validation was read-only except for the normal failed-login audit generated while testing the documented development bootstrap credential. No deliverable generation, lifecycle transition, sign-off, customer acceptance, fixture, or fake evidence was created.

## Blockers and disposition

- No valid production human credential was available, so authenticated PM/QA owner truth and field-for-field normalized comparison are unproven.
- The representative Infra design pointer is invalid in production and must be corrected by an authorized user.
- Cloudflare authentication was unavailable and Pages did not auto-deploy the pushed revision; frontend revision and browser behavior are unproven.
- No browser automation/session was available.
- Infra fakecloud/OpenTofu acceptance infrastructure was unavailable locally.

Disposition: implementation `ACCEPTED`; runtime `PARTIAL`; production `PARTIAL`; full closure `PARTIAL`.

## V2 addendum — credential, binding, frontend, and infrastructure closure

V2 started from a clean `0740aea40c49d7a86f9103e5266f9e06fa9261b8`. The application implementation was unchanged. A focused CI syntax repair was committed as `be81e3c56e91e19696a719e57ea3a20beb4d04f0`; the replacement GitHub Actions run succeeded.

The actual read architecture is delegated human SSO, not a backend service credential. An existing local credential store allowed direct, authenticated PM and QA reads, proving all stored PM/QA targets resolve. It did not contain a usable Account Again ecosystem password, and macOS Keychain would not grant the saved Chrome credential non-interactively. No token was minted, extracted, combined, or bypassed.

Direct owner results were PM green with empty schedule/milestone/dependency counts and nonempty effort, plus authoritatively empty QA results across all five scopes. Infra's authoritative design catalog is empty, proving that the stale 404 pointer must become explicitly unbound rather than rebound by inference. The binding update remains blocked because the supported Document workflow requires the unavailable ecosystem session.

Cloudflare remains blocked: Wrangler is logged out, no Cloudflare token exists in the environment, and the installed GitHub App produced no run or deployment. Bundle hashes independently prove that production still serves the prior frontend.

The Infra extended-test blocker is closed. With repo-documented fakecloud and OpenTofu, the full suite completed with 361 passed and 8 skipped.

V2 remains `PARTIAL`: successful direct owner reads improve runtime evidence, but production normalization, frontend revision, binding correction, Overview/precheck UI, and browser proof remain blocked.
