# OIDA 1.0 Operations Runbook

Run commands from the repository root unless a working directory is shown. Never place credentials in commands, logs, artifacts, or Git.

## 1. Production topology and health

The public surface is `https://oida.kanphong.com` → `https://api-oida.kanphong.com` → private Fly services. Direct Fly health endpoints are public process checks only; business routes remain authenticated.

```bash
curl -fsS https://oida-gateway.fly.dev/healthz
curl -fsS https://oida-document.fly.dev/api/health
curl -fsS https://oida-pm.fly.dev/api/health
curl -fsS https://oida-qa.fly.dev/api/health
curl -fsS https://oida-account.fly.dev/api/v1/health
curl -fsS https://oida-conductor.fly.dev/api/health
curl -fsS https://oida-infra.fly.dev/health
curl -fsS -A 'Mozilla/5.0' https://oida.kanphong.com
```

Inspect Fly machines and checks with the OIDA configs:

```bash
flyctl status -c services/document-again/fly.toml
flyctl status -c ops/fly/oida-gateway/fly.toml
flyctl status -c services/pm-again/backend/fly-oida.toml
flyctl status -c services/qa-again/backend/fly-oida.toml
flyctl status -c services/account-again/fly-oida.toml
flyctl status -c services/conductor-again/backend/fly-oida.toml
flyctl status -c services/infra-again/fly-oida.toml
```

## 2. Revision verification

```bash
git status --short
git rev-parse HEAD
git log -5 --oneline
flyctl releases -a oida-document --image
npx wrangler pages deployment list --project-name oida
curl -fsS -A 'Mozilla/5.0' https://oida.kanphong.com | rg -o 'assets/index-[A-Za-z0-9_-]+\.(js|css)'
```

For an exact web proof, the Pages Source column must match the intended implementation SHA and the custom-domain assets must match that deployment's build. Fly release numbers identify deployed images; if a source SHA is not embedded in an image, record source-to-image mapping as deployment-log evidence rather than inventing it.

## 3. OIDA Web deployment

```bash
cd apps/oida-web
npm test -- --run
npm run lint
npm run build
npx wrangler pages deploy dist --project-name oida --branch main --commit-hash "$(git -C ../.. rev-parse HEAD)"
```

Then verify Pages deployment status, custom-domain HTTP 200, and asset hashes. Production builds must retain the configured API base established by the deployment environment; reject a build that sends `/api/*` to Pages instead of the gateway.

## 4. Document Again deployment

```bash
cd services/document-again
flyctl deploy --remote-only
cd ../..
flyctl status -c services/document-again/fly.toml
flyctl releases -a oida-document --image
curl -fsS https://oida-document.fly.dev/api/health
```

Accept only after the machine is `started`, all checks pass, and protected gateway requests still fail closed anonymously.

## 5. Gateway validation and deployment

The gateway normally does not redeploy for Document/Web-only releases.

```bash
pytest -q ops/fly/oida-gateway/test_main.py
curl -fsS https://oida-gateway.fly.dev/healthz
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://api-oida.kanphong.com/api/da/portfolio/command-center
```

The anonymous business request must return `401`. If gateway source changes are explicitly approved:

```bash
cd ops/fly/oida-gateway
flyctl deploy --remote-only
```

## 6. Failure diagnostics

| Signal | Meaning | Safe response |
| --- | --- | --- |
| HTTP 401 | Missing/expired/invalid Account session | Reauthenticate normally; do not bypass or inject identity headers |
| HTTP 403 | Authenticated actor lacks project/tenant permission | Verify membership and tenant scope; do not broaden authorization |
| `UNAVAILABLE` | Bound owner or network failed | Check owner health/logs; preserve partial status |
| `UNBOUND` | No explicit owner binding | Ask an authorized human to select one, or leave optional source unbound |
| `INVALID` | Explicit binding no longer resolves or violates contract | Refresh owner inventory and correct the binding explicitly |
| `EMPTY` | Owner answered successfully with no records | Treat as authoritative empty, never as failure |
| `UNKNOWN` | Evidence cannot support a value | Preserve unknown; do not substitute zero |
| `UNKNOWN_RESULT` | Owner write outcome is ambiguous | Reconcile owner truth and action history before any manual retry |
| `RECHECK_REQUIRED` | Evidence changed since resolution evaluation | Recheck authoritative truth; do not call resolved |
| `AI_NOT_CONFIGURED` | No eligible provider | Continue with deterministic brief; do not block the product |
| `AI_UNAVAILABLE` | Configured provider failed | Use deterministic fallback and inspect provider health separately |

Use `flyctl logs -a <app>` and the request correlation ID. Never print authorization headers, cookies, tokens, signing material, or secrets.

## 7. Binding and owner diagnosis

Read `project_bindings/v1` first. Keep BOUND, UNBOUND, INVALID, and UNAVAILABLE distinct. Never infer a binding from a display name or slug. Compare normalized facts with the authorized owner API; do not query another service's database or create shadow truth.

For an owner action, verify: human confirmation is current, preview is READY, evidence hash matches, action is allowlisted, target binding is explicit, and owner API is used. After execution, inspect action events and refreshed truth. `SUCCEEDED` does not mean the impact resolved.

## 8. Rollback

Before rollback, record current release/deployment IDs and reason.

Fly has no `flyctl releases rollback` command in the installed CLI. List images, then redeploy the previously known-good immutable image explicitly:

```bash
flyctl releases -a oida-document --image
flyctl deploy -c services/document-again/fly.toml --image registry.fly.io/oida-document:<known-good-image>
flyctl status -c services/document-again/fly.toml
```

For OIDA Web, Wrangler does not expose a promotion/rollback subcommand. Rebuild the known-good Git revision in a temporary worktree and create a new production deployment; do not delete the current deployment first:

```bash
git worktree add <temporary-path> <known-good-sha>
cd <temporary-path>/apps/oida-web
npm ci
npm test -- --run
npm run build
npx wrangler pages deploy dist --project-name oida --branch main --commit-hash <known-good-sha>
```

Remove the temporary worktree after validation using normal `git worktree remove <temporary-path>`. Verify custom-domain assets and anonymous HTTP 401 again. Database rollback is not implied by an application rollback; never delete or rewrite production data as part of this runbook.

## 9. OIDA 1.0 known-good references

- R19 accepted head: `9f7a505fde9782d8ce370d9a0ea0fc038b24118b`.
- Product implementation: `ef3429867c7efa6fb44f94edfe20a0be0932723c`.
- Document Again: release 31, image `deployment-01M0MK0ZTGMTDQ2QF8ANENNSMT`.
- OIDA Web: `c56491ef-a48a-4db8-a152-8f56834b98fb`, assets `index-DfgOg1Ze.js` and `index-CiWTekrW.css`.
- Gateway: release 8, image `deployment-01M0KHJHVHKMQRRPP1SC1FHQX0`.
