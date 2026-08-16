# QA Runner — HYB-0 spike

Minimal Node.js + Playwright runner proving the hybrid manual+automation
architecture works end-to-end. See `docs/hybrid/HYB-0-GAP-ANALYSIS.md`
for the design decisions and `docs/hybrid/HYB-0-SPIKE-RESULTS.md` for the
recorded proof run. This is **not** HYB-1's real runner — no recorder, no
workflow model, no registration/heartbeat, exactly one hardcoded scenario
(QA-Again's own login flow).

## Setup

```bash
cd runner
npm install
npx playwright install chromium
cp .env.example .env   # fill in RUNNER_TOKEN (see below)
```

Mint a runner token (backend must be running, and you need an ADMIN
session cookie):

```bash
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"..."}'

curl -b cookies.txt -X POST http://127.0.0.1:8000/api/runner-tokens \
  -H "Content-Type: application/json" \
  -d '{"label":"local-spike"}'
# -> {"id":1,"label":"local-spike","token":"..."}  <- put this in .env as RUNNER_TOKEN
```

The project named in `PROJECT_SLUG` must already exist (create it via the
QA-Again UI or `POST /api/projects`).

## Run

With the backend (`uvicorn`) and frontend (`npm run dev`) both running:

```bash
npm run spike
```

A visible Chromium window opens, fills the login form, then pauses. The
console prints the exact `curl` command to approve or reject the
checkpoint as a logged-in QA-Again user. Approve with `PASS` to watch it
resume, submit login, capture a screenshot, and upload it.
