# QA-Again — Viewer Guide

VIEWER is QA-Again's read-only role — a stakeholder who needs visibility
into QA progress without editing anything.

## Signing in

Go to the app URL, sign in with the email/password an admin gave you. If
this is your first login, you'll be asked to set a new password before
anything else works — that's expected.

## What you can see

- **Projects** (`/`) — every non-archived project you have access to.
- **Dashboard** (a project's default page) — total cases, PASS/NG/
  Blocked/Not Run/N-A counts, pass rate, evidence completeness, go-live
  readiness and its blockers, open defects by severity, storage usage,
  recent activity. Hover a percentage tile to see the exact formula
  used.
- **Test Suites** and their revisions/cases — read-only.
- **Test Cycles** — open a cycle's execution screen to see every case's
  current status, actual result, and attached evidence (click a
  thumbnail to view it full-size with any annotations, but you cannot
  add new annotations).
- **Reports** — pick a report type and a cycle from the dropdowns, click
  **Run Report**. All the same reports admins and testers see.
- **Export Excel** / **Export ZIP Package** — both export buttons on the
  Reports page work for you too; exports are read operations.

## What you cannot do

Any button that would change data (New Suite, New Cycle, PASS/NG/
Blocked/N-A, uploading evidence, drawing an annotation, archiving
evidence, creating a defect, recording a sign-off, locking/reopening a
cycle) is either hidden or will return a permission error if attempted
directly. This is enforced by the backend, not just hidden in the UI —
don't rely on hidden buttons for security, but you shouldn't need to;
they're hidden precisely because they won't work for you.

## If something looks wrong

If a project or cycle you expect to see is missing, ask an admin — it
may be archived, or you may not have been granted access to that
specific... actually QA-Again's roles are global, not per-project (every
VIEWER sees every non-archived project) — if a whole project is
missing, it's archived; ask an admin to check the "Show archived"
project list.
