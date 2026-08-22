# OIDA R17.1.2 — Full Closure

Date: 2026-08-22 (Asia/Bangkok)

## Scope and revisions

V4 began from clean `main` at `97128c58572c469a24538d301dffb76a3bf6e4a1`. The only application correction is `18a96bb1630debd4bb598019bc8e653c6851916c`: an explicit `project_bindings/v1` Infra `UNBOUND` update now removes the contradictory legacy `infra_design_id`. The focused regression test proves this behavior. Documentation commits do not change the deployed application tree.

## Supported access and deployment

- Wrangler OAuth completed normally for `Gunaex@gmail.com's Account`; the existing Pages project is `oida`, production branch `main`, with `oida.kanphong.com` and `oida-50j.pages.dev`.
- Account Again's normal human session returned `/api/auth/me` and propagated one ecosystem bearer identity to Document, PM, QA, and Conductor. No credential boundary was bypassed and no credential value was recorded.
- Document Again was deployed as Fly release v19, image `deployment-01M0KS85DEAXJ789VQMKBZ096S`, manifest `sha256:0c4abcd19e4bd378ec645eff0381e6e80b27cc4b01e5fea0dcf7748c00ed9895`.
- The final Pages deployment is `f15c3bf4-c4ed-4931-87f4-b2121c214647`, URL `https://f15c3bf4.oida-50j.pages.dev`, production branch `main`, source `18a96bb`.
- The production build explicitly used `VITE_API_BASE=https://api-oida.kanphong.com`. Expected and observed assets are `index-Dk2c4Q1U.js` and `index-DY3WuLkC.css`.

## Binding correction

Before V4, Infra retained legacy pointer `DESIGN-EBAE25`; the authoritative Infra design catalog was empty, so truth correctly classified it `INVALID`. A supported authenticated workspace-binding PUT saved explicit Infra `UNBOUND`, source `USER_SELECTED`, external ID `null`, and removed the legacy pointer. The response was HTTP 200. PM remains bound to `true-cloud-migration`; QA remains bound to five explicit scopes. Infra now incurs zero downstream calls.

## Authenticated project truth

Project `prj_853bcc5700a54c8db170` returned `project_truth/v1` with HTTP 200. Service duration was 137.6 ms; external request latency was 316.882 ms. It reported:

- PM `OK`: green project; schedule `EMPTY` with zero items; zero milestones; progress zero across phases; effort `AVAILABLE` with zero totals; dependencies `EMPTY`.
- QA `OK`: readiness `NOT_STARTED`; definitions/evidence `EMPTY`; zero suites, tests, open defects, and blocking defects; no result counts or pass rate.
- Infra `UNBOUND`: no fabricated Infra truth and no owner call.
- Freshness `UNKNOWN` for all domains because the owner APIs supplied no meaningful source-update timestamp. No timestamp was invented.
- Downstream calls: PM 3, QA 15, Infra 0, total 18. The snapshot is intentionally partial because Infra is unbound.

Direct owner comparisons matched the normalized fields exactly. PM dashboard, Gantt, and effort calls returned HTTP 200 and took 198.3 ms, 127.1 ms, and 135.9 ms. All 15 QA calls returned HTTP 200; per-call latency ranged from 117.8 to 181.3 ms. This proves authoritative QA empty data normalizes to `OK` plus empty/not-started dimensions, unlike the deterministic 401 path, which remains `UNAUTHORIZED`.

## Precheck and shared truth layer

Authenticated HD-MIG-01 precheck returned HTTP 200 with external latency 322.504 ms and `NOT_READY`: 0 ready, 14 missing, 0 no-source, 0 unknown at the internal-module summary level. The cross-service factors trace directly to the same normalized snapshot:

| Factor | Owner truth | Result |
|---|---|---|
| Migration Schedule | PM `OK`, schedule `EMPTY` | `MISSING` — “PM Again reports EMPTY.” |
| QA Readiness | QA `OK`, readiness `NOT_STARTED` | `MISSING` — “QA Again reports NOT_STARTED.” |
| Target Architecture | Infra binding `UNBOUND` | `UNKNOWN` — cannot verify an unbound source |
| Infrastructure Connectivity | Infra binding `UNBOUND` | `UNKNOWN` — cannot verify an unbound source |

Truth plus precheck external latency was 639.386 ms. The UI and direct API evidence agree on PM `OK`, QA `OK`, Infra `UNBOUND`.

## Browser acceptance

An authenticated headless Chrome loaded the production custom domain and exact final assets. Overview rendered the cross-service truth and explicit Infra-unbound state. Documents rendered ten deliverables; HD-MIG-01 opened with its existing baselined v1.0 and `NOT READY` precheck. Browser-triggered precheck completed through `OPTIONS 200`, `POST 200`, followed by successful detail/catalog/list refreshes. All observed application API requests targeted `https://api-oida.kanphong.com`; there were zero JavaScript exceptions and zero console errors/warnings in the final passes.

An initial deployment built without `VITE_API_BASE` was rejected during this same acceptance pass because Pages returned SPA HTML for same-origin `/api/*` calls. It was immediately replaced by the final production-gateway build above; the failed observation is retained here to make the revision proof auditable.

## Verification and integrity

- Document Again: 133 passed; focused truth tests: 13 passed.
- Gateway: 3 passed. PM: 38 passed. QA: 101 passed plus the accepted 5-test target. Infra: 361 passed plus the accepted 8-test target.
- Frontend: `npm ci` reported zero vulnerabilities; lint passed with the accepted warning backlog; production build passed with 1,783 modules.
- CI run `32549907308` for application source `18a96bb` completed successfully.
- Security scan found no committed secret, token, cookie, or password. No auth disablement, fallback credential, database mutation, fake Infra design, or tenant bypass was introduced.
- No deliverable generation, lifecycle transition, waiver, customer sign-off, customer acceptance, or fabricated evidence occurred. The browser precheck only refreshed derived readiness evidence.

## Acceptance

- Implementation: `ACCEPTED`
- Runtime: `ACCEPTED`
- Production: `ACCEPTED`
- Full closure: `ACCEPTED`
- Remaining blockers: none for R17.1.2

No next phase is started by this closure.
