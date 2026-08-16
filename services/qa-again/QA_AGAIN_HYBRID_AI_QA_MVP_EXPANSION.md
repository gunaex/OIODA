# QA-Again — Hybrid AI QA MVP Expansion
## Product Vision, Architecture Direction, Delivery Scope, and Team Handover

**Document status:** Product-direction proposal and implementation handover  
**Version:** 0.2  
**Date:** 2026-08-01  
**Companion document:** `QA_AGAIN_REBUILD_PROMPT_FASTAPI_REACT.md`  
**Primary implementation baseline:** FastAPI + React/Vite, matching PM-Again conventions

---

## 0. Purpose of this document

The current QA-Again rebuild specification correctly defines an evidence-first
manual QA platform with:

- test suites and immutable script revisions;
- test cycles bound to exact revisions;
- manual execution statuses;
- screenshot evidence and annotation;
- defects, sign-offs, dashboards, reports, and exports;
- independent projects, authentication, and databases;
- a FastAPI + React/Vite architecture aligned with PM-Again.

That baseline remains valid.

However, experience from the SATL project exposed a larger problem that the
current manual-only scope does not yet solve:

> AI-assisted development produces changes faster than a human QA process can
> repeatedly verify them.

The practical failure pattern is:

1. An issue is fixed quickly.
2. The new change creates a side effect in an older function.
3. AI or the developer focuses on the current issue and does not revisit the
   affected regression path.
4. A previous function silently breaks.
5. The customer finds the regression after delivery.
6. The team must repeat the same manual test and evidence-capture work again.

This document expands QA-Again from an evidence-first manual QA application
into a **hybrid manual-and-automation QA platform** while preserving human
review, evidence integrity, auditability, and the existing PM-Again-aligned
technical foundation.

This is not permission to discard the current rebuild specification. It is a
companion document that defines the next product direction and identifies the
few existing decisions that must be deliberately superseded.

---

## 1. Product thesis

QA-Again should not be positioned only as a test-case management tool.

Its purpose is:

> Give the team defensible confidence that a new software change has not
> damaged previously working behavior.

The platform manages five connected things:

1. **Intent** — what should be tested and what result is expected.
2. **Execution** — what the automation runner and tester actually did.
3. **Evidence** — what was visibly observed during the run.
4. **History** — how behavior and response time changed between runs.
5. **Accountability** — who or what produced each result and who approved it.

The product principle is:

> AI may prepare, suggest, summarize, and accelerate. It must not fabricate a
> test result or silently replace human acceptance.

---

## 2. Important change to the existing specification

The current rebuild document carries forward an explicit non-goal:

```text
No Playwright E2E automation platform.
```

That non-goal conflicts with the new product direction.

If this expansion is approved, supersede only that specific non-goal with the
following decision:

> QA-Again may orchestrate Playwright-based browser workflows through a
> controlled runner, including hybrid pauses for manual verification.

The following existing constraints remain unchanged unless separately decided:

- no continuous video recording;
- no shared database or shared session with PM-Again;
- no two-way synchronization with PM-Again;
- no silent mutation of published test revisions;
- no replacement of evidence originals;
- no automatic acceptance based only on an AI statement;
- no uncontrolled browser automation running inside the public API process.

This direction change must be recorded in an ADR before implementation begins.

Suggested ADR:

```text
docs/adr/ADR-HYB-001-playwright-hybrid-execution.md
```

---

## 3. Real problem statement from SATL

The current project workflow creates excessive repetitive QA work:

- The same pages and flows must be checked after every fix.
- Screenshots are manually captured and pasted into Excel.
- Evidence must be recreated even when the same regression path is repeated.
- A fix in one area can damage another previously completed area.
- API regression alone does not prove that the real browser experience works.
- AI coding agents may report that everything passes without supplying enough
  verifiable evidence.
- A tester cannot easily see when a button or page has become progressively
  slower across releases.
- Manual-only evidence creation consumes the time that QA should spend on
  judgement and risk analysis.

The required solution is not full autonomous testing.

The required solution is a controlled hybrid workflow in which:

```text
Automation performs repeatable browser actions
        ↓
The workflow pauses at a defined checkpoint
        ↓
A tester verifies the screen or business outcome
        ↓
Evidence is captured and annotated
        ↓
The tester approves, rejects, or blocks the checkpoint
        ↓
Automation resumes from the next step
```

---

## 4. Product boundaries

### 4.1 QA-Again remains the control plane

The existing FastAPI + React application remains responsible for:

- projects and users;
- test suites and immutable revisions;
- workflow definitions and versions;
- cycles and execution assignments;
- manual checkpoints;
- results and result history;
- evidence metadata and annotation revisions;
- defects and sign-offs;
- reports and exports;
- audit logs;
- runner registration and run coordination.

### 4.2 A separate QA Runner performs browser execution

Do not run long-lived browser automation directly inside the main FastAPI web
process.

Introduce a separate component:

```text
QA Runner
```

The QA Runner should be a small Node.js application using Playwright. It may run:

- locally on a tester's Windows or macOS machine;
- on an internal server;
- in a dedicated self-hosted container;
- later, in a managed runner pool.

For the MVP, prioritize a local runner because it can:

- open a visible browser for human checkpoints;
- access applications available only through VPN or an internal network;
- use the tester's actual screen and browser environment;
- avoid exposing internal target systems to the public backend;
- pause and resume while the tester examines the application;
- upload evidence to QA-Again through authenticated APIs.

### 4.3 Communication direction

Prefer outbound communication from the runner to the backend.

The runner should:

1. authenticate using a revocable runner token;
2. request or receive an assigned execution;
3. download the immutable workflow snapshot;
4. execute steps locally;
5. post step events, timings, logs, and evidence;
6. wait at manual checkpoints;
7. resume only after an authorized tester decision;
8. finalize the run with machine-verifiable status information.

Do not require inbound access from the internet to the tester's machine.

---

## 5. MVP capability set

The first hybrid MVP should contain the following capabilities only.

### 5.1 Hybrid workflow execution

A workflow consists of ordered, immutable steps copied into an execution
snapshot.

Supported MVP step types:

| Step type | Purpose |
|---|---|
| `NAVIGATE` | Open a URL or application route. |
| `CLICK` | Click an element using a semantic locator. |
| `FILL` | Enter text into an input. |
| `SELECT` | Choose a dropdown or selectable option. |
| `CHECK` | Set a checkbox or similar boolean control. |
| `UPLOAD` | Upload a designated test file. |
| `WAIT_FOR` | Wait for an element, URL, response, or visible state. |
| `ASSERT` | Evaluate a deterministic browser assertion. |
| `CAPTURE` | Capture a screenshot evidence item. |
| `MANUAL_CHECKPOINT` | Pause for human verification and decision. |
| `MANUAL_INPUT` | Ask a human to perform or supply something automation should not own. |
| `NOTE` | Present execution guidance without performing an action. |

The MVP does not need loops, branching, reusable parameters across projects, or
arbitrary code execution. Those can be added only after the core execution
model proves stable.

### 5.2 Manual checkpoint

A manual checkpoint must contain:

- checkpoint title;
- instruction to the tester;
- expected result;
- whether evidence is required;
- minimum number of screenshots, if any;
- optional reference image or previous approved evidence;
- allowed decisions;
- required reason rules;
- timeout behavior;
- resume behavior.

Allowed decisions:

```text
PASS
FAIL
BLOCKED
NOT_APPLICABLE
```

Rules:

- `PASS` is a human decision and records the tester identity and timestamp.
- `FAIL` requires an actual result and may create or link a defect.
- `BLOCKED` requires a blocking reason.
- `NOT_APPLICABLE` requires a reason and follows the existing approval rule.
- The runner cannot convert a manual checkpoint to `PASS` by itself.
- AI cannot submit a manual checkpoint decision.

### 5.3 Pause and resume

The run must support these states:

```text
QUEUED
CLAIMED
STARTING
RUNNING
WAITING_FOR_HUMAN
RESUMING
PASSED
FAILED
BLOCKED
CANCELLED
RUNNER_LOST
```

Required behavior:

- Every state transition is append-only in execution history.
- A run waiting for a human must preserve browser context when technically
  possible.
- A lost runner must not be recorded as a functional failure.
- A resumed run must continue from the next approved step, not restart silently.
- Manual restart must create a new run attempt while preserving the earlier one.
- A locked or signed-off cycle rejects new mutation according to the existing
  cycle rules.

### 5.4 Workflow recorder

The tester should be able to start a recording session and perform a flow in a
real browser.

The recorder captures semantic browser interactions rather than screen
coordinates.

Recordable MVP actions:

- navigation;
- click;
- text entry;
- select;
- checkbox/radio interaction;
- file upload intent;
- keyboard shortcut when meaningful;
- explicit screenshot marker;
- manual checkpoint marker.

The recorder must not use raw `x/y` position as the primary locator.

Preferred locator hierarchy:

1. explicit `data-testid` or configured stable test attribute;
2. accessible role and accessible name;
3. associated label;
4. stable placeholder or input name;
5. stable visible text when unique;
6. constrained CSS selector;
7. XPath only as a documented fallback.

Each recorded step should store:

- action type;
- primary locator strategy and value;
- fallback locators;
- human-readable element description;
- page URL or route context;
- captured input policy;
- whether the value is literal, secret, variable, or runtime input;
- optional screenshot thumbnail;
- recorder confidence and warnings;
- creation metadata.

Sensitive values must not be stored as clear text. Password fields and values
marked secret must become named secret references.

Example:

```yaml
step_type: CLICK
description: Click Save button
locator:
  primary:
    strategy: test_id
    value: customer-save
  fallbacks:
    - strategy: role
      role: button
      name: Save
page_context:
  path: /customers/new
```

### 5.5 Evidence-first execution

The existing evidence model remains central.

Automation adds new evidence sources:

- automatic screenshot before a failed action;
- automatic screenshot after a failed assertion;
- explicit workflow capture steps;
- screenshots submitted at manual checkpoints;
- optional DOM or console diagnostic text as attachments;
- step log and timing history.

Evidence rules remain:

- original files are immutable;
- annotation state is append-only revision JSON;
- evidence is served only through authenticated routes;
- MIME signature and size are validated;
- evidence is associated with a project, cycle, run, case, and step where
  applicable;
- deletion follows an explicit retention or administrative process, never an
  overwrite operation.

### 5.6 Annotation

The existing annotation requirements remain in scope:

- arrow;
- rectangle;
- highlight;
- freehand drawing;
- text;
- numbered callout;
- blur/redaction;
- orange as the default annotation color;
- undo and redo;
- append-only annotation revisions.

For the MVP, annotation remains human-controlled.

AI-assisted annotation is a later feature and must always produce a draft that
requires user confirmation.

### 5.7 Repeatable regression suite

A published workflow revision may be assigned to one or more test cases.

A regression suite should allow a team to compose reusable flows such as:

- login;
- create/read/update/delete;
- search and filter;
- file upload;
- import validation;
- export;
- approval;
- dashboard verification;
- permission and role checks.

At cycle creation, QA-Again snapshots exact published revisions of both:

- test scripts; and
- automation workflows.

A later edit must never change an existing cycle.

### 5.8 Response-time history

This feature is observational, not a full load-testing system.

For every automated step, capture at minimum:

- started timestamp;
- completed timestamp;
- duration in milliseconds;
- wait category, when known;
- retry count;
- final action outcome.

Display history such as:

```text
Save customer
Run 12: 1.18 s
Run 13: 1.31 s
Run 14: 2.74 s
```

The MVP should show trend and difference without automatically declaring a
performance defect.

Optional user-configured thresholds may be added later.

This is not a replacement for concurrency, stress, soak, or capacity testing.

### 5.9 Reports and export

Extend the existing report/export design with:

- workflow revision used;
- runner identity and version;
- browser and operating-system information;
- run start/end time;
- step count and step outcomes;
- manual checkpoint decisions and approvers;
- duration per step;
- evidence references;
- automation failure details;
- retries;
- final run status;
- distinction between machine assertions and human approvals.

A report must never collapse these into a single unexplained `PASS`.

---

## 6. Result trust model

The platform must distinguish who or what produced a result.

Suggested result provenance values:

```text
AUTOMATION_ASSERTION
HUMAN_VERIFICATION
SYSTEM_ERROR
IMPORTED_RESULT
AI_SUGGESTION
```

Rules:

1. `AUTOMATION_ASSERTION` is valid only when produced by the runner from an
   executed assertion and supporting event log.
2. `HUMAN_VERIFICATION` requires a logged-in user action.
3. `SYSTEM_ERROR` is not a product failure and must remain separately visible.
4. `IMPORTED_RESULT` is labeled as imported and cannot pretend to be a live run.
5. `AI_SUGGESTION` is never a final execution result.
6. A final cycle status must be reproducible from stored result records.
7. No AI-generated sentence such as “everything passed” is accepted without the
   underlying step, assertion, and evidence records.

This is the primary control against fake or overly optimistic AI test reports.

---

## 7. AI assistance scope

AI is useful, but it must sit outside the authoritative execution path.

### 7.1 MVP-safe AI functions

AI may draft:

- test cases from requirements;
- expected results;
- negative cases;
- boundary cases;
- validation rules;
- checkpoint instructions;
- workflow step descriptions;
- failure summaries;
- evidence captions;
- defect descriptions;
- regression-suite suggestions.

All generated content must be labeled `DRAFT` until reviewed by a tester or
administrator.

### 7.2 AI functions not allowed to finalize

AI must not:

- mark a manual checkpoint as passed;
- sign off a cycle;
- modify a published revision in place;
- delete evidence;
- hide a failed step;
- turn a runner error into a product pass;
- invent browser execution that did not occur;
- claim that a regression suite ran without corresponding execution records.

### 7.3 Requirement-to-test workflow

Suggested flow:

```text
Requirement / user story / meeting note
        ↓
AI produces a draft test package
        ↓
QA reviews expected results and risks
        ↓
QA edits and approves
        ↓
A new immutable test revision is published
        ↓
The workflow recorder or editor links execution steps
        ↓
A cycle snapshots the approved revisions
```

The role traditionally performed by an SA is not eliminated. Its critical
function becomes explicit source-of-truth stewardship and review of AI-produced
artifacts.

---

## 8. Proposed domain-model additions

The following names are directional. Match final naming to the existing model
conventions during implementation.

### 8.1 `workflow_definitions`

Mutable top-level identity for a reusable browser workflow.

Suggested fields:

- `id`
- `workflow_key`
- `name`
- `description`
- `status`
- `created_by`
- `created_at`
- `updated_at`

### 8.2 `workflow_revisions`

Immutable after publication.

Suggested fields:

- `id`
- `workflow_definition_id`
- `revision_number`
- `status` (`DRAFT`, `PUBLISHED`, `RETIRED`)
- `source` (`RECORDED`, `MANUAL_EDITOR`, `IMPORTED`)
- `browser_policy_json`
- `created_by`
- `created_at`
- `published_by`
- `published_at`

### 8.3 `workflow_steps`

Ordered children of a workflow revision.

Suggested fields:

- `id`
- `workflow_revision_id`
- `step_order`
- `step_type`
- `title`
- `instruction`
- `expected_result`
- `locator_json`
- `input_policy_json`
- `assertion_json`
- `checkpoint_policy_json`
- `timeout_ms`
- `capture_policy`
- `created_at`

### 8.4 `test_case_workflow_links`

Links a test case revision to an exact workflow revision.

Suggested fields:

- `id`
- `test_case_id`
- `workflow_revision_id`
- `execution_mode` (`MANUAL`, `AUTOMATED`, `HYBRID`)
- `created_at`

### 8.5 `runners`

Registered execution agents.

Suggested fields:

- `id`
- `runner_key`
- `display_name`
- `status`
- `platform`
- `runner_version`
- `playwright_version`
- `capabilities_json`
- `last_seen_at`
- `created_by`
- `created_at`
- `revoked_at`

Runner secrets must be hashed or otherwise stored according to the same security
principles used for refresh tokens.

### 8.6 `execution_runs`

One attempt against a cycle test result and workflow snapshot.

Suggested fields:

- `id`
- `cycle_id`
- `cycle_test_result_id`
- `workflow_revision_id`
- `runner_id`
- `attempt_number`
- `status`
- `browser_name`
- `browser_version`
- `operating_system`
- `started_at`
- `ended_at`
- `claimed_at`
- `last_heartbeat_at`
- `initiated_by`
- `finalized_by`

### 8.7 `execution_step_results`

Append-oriented record for each step attempt.

Suggested fields:

- `id`
- `execution_run_id`
- `workflow_step_id`
- `step_order`
- `attempt_number`
- `status`
- `result_provenance`
- `started_at`
- `ended_at`
- `duration_ms`
- `actual_result`
- `error_category`
- `error_message`
- `locator_used_json`
- `diagnostic_json`

### 8.8 `manual_checkpoint_decisions`

Never edited in place.

Suggested fields:

- `id`
- `execution_run_id`
- `execution_step_result_id`
- `decision`
- `actual_result`
- `reason`
- `decided_by`
- `decided_at`

### 8.9 `runner_events`

Append-only technical event stream for troubleshooting and audit.

Suggested event types:

```text
RUN_CLAIMED
BROWSER_STARTED
STEP_STARTED
STEP_COMPLETED
STEP_RETRIED
CHECKPOINT_WAITING
CHECKPOINT_RELEASED
EVIDENCE_UPLOADED
HEARTBEAT
RUNNER_DISCONNECTED
RUN_COMPLETED
```

Do not use runner events as a substitute for normalized business result tables.

---

## 9. Recorder and locator resilience

A recorded flow is useful only when it survives reasonable UI movement.

### 9.1 Do not depend on mouse position

Raw coordinates may be retained only as optional diagnostics. They must not be
the primary replay mechanism.

### 9.2 Detect weak locators

The recorder should warn when:

- visible text is duplicated;
- a CSS selector contains unstable generated classes;
- an XPath is deeply nested;
- an element has no stable identity;
- a selected element changes between captures;
- the action targets a canvas or unsupported surface.

### 9.3 Encourage testability contracts

QA-Again should recommend that applications expose stable test attributes such
as:

```html
<button data-testid="customer-save">Save</button>
```

This is a development-quality contract, not a visual implementation detail.

### 9.4 Controlled self-healing is later scope

The MVP may try declared fallback locators in order.

It must not use opaque AI locator replacement and silently continue. If a
fallback is used, the run record must show:

- which locator failed;
- which fallback succeeded;
- whether the workflow needs maintenance.

AI-assisted locator repair may be explored later as a reviewable suggestion.

---

## 10. Security and privacy requirements

Hybrid automation introduces new risks beyond the existing manual platform.

Minimum controls:

- runner tokens are revocable and scoped;
- a runner receives only assigned project/workflow data;
- secrets are referenced, never embedded in workflow JSON;
- password inputs are redacted from logs and screenshots where possible;
- evidence uploads use authenticated APIs and validated MIME signatures;
- target URLs follow project allowlists where practical;
- arbitrary JavaScript execution is not supported in the MVP;
- uploaded test files are controlled project assets;
- runner version and integrity information are recorded;
- lost or revoked runners cannot claim new jobs;
- manual checkpoint decisions require normal user authentication;
- PDPA-sensitive screenshots support blur/redaction before report export;
- audit history records workflow publication, run initiation, checkpoint
  decisions, evidence revision, and sign-off.

A fresh threat model is required before production rollout.

Suggested file:

```text
docs/HYBRID_RUNNER_THREAT_MODEL.md
```

---

## 11. MVP user journeys

### 11.1 Record and publish a hybrid workflow

```text
Tester opens a test case
        ↓
Selects “Record Workflow”
        ↓
QA Runner opens a visible browser
        ↓
Tester performs the normal web flow
        ↓
Tester inserts one or more manual checkpoints
        ↓
Recorder creates a draft workflow revision
        ↓
Tester reviews locators, inputs, and expected results
        ↓
Tester publishes the immutable workflow revision
```

### 11.2 Execute a regression cycle

```text
Tester creates a cycle from published test revisions
        ↓
QA-Again snapshots linked workflow revisions
        ↓
Tester assigns or starts a run
        ↓
Local QA Runner claims the run
        ↓
Automation executes repeatable steps
        ↓
The browser pauses at a manual checkpoint
        ↓
Tester captures/annotates evidence and decides
        ↓
Automation resumes
        ↓
QA-Again stores final machine and human results separately
        ↓
Tester reviews and signs off the cycle
```

### 11.3 Investigate a regression

```text
A step fails or takes longer than earlier runs
        ↓
QA opens run history
        ↓
Compares timings, screenshots, locator use, and actual result
        ↓
Creates or links a defect
        ↓
A corrected workflow is cloned into a new draft revision if required
        ↓
The original run and revision remain unchanged
```

---

## 12. MVP acceptance criteria

### 12.1 Workflow authoring

- A tester can create a draft workflow by recording a browser flow.
- Recorded steps use semantic locators, not raw coordinates.
- A tester can edit descriptions, expected results, timeouts, and locators.
- A tester can insert a manual checkpoint.
- A published workflow revision cannot be edited.
- A correction creates a new draft revision.

### 12.2 Runner

- A registered local runner can authenticate and claim an assigned run.
- The runner opens a visible Chromium browser.
- The runner executes navigation, click, fill, select, wait, assert, and capture
  steps.
- The runner sends heartbeats and step events.
- The runner pauses at a manual checkpoint.
- The runner resumes only after an authorized decision.
- A disconnected runner produces `RUNNER_LOST`, not a false product failure.

### 12.3 Evidence

- Automatic failure screenshots are stored against the failed step.
- Manual checkpoint screenshots can be captured or uploaded.
- Evidence originals are immutable.
- Annotation revisions are append-only.
- Exported reports identify the associated run, case, and step.

### 12.4 Trust and audit

- Machine assertions and human decisions are visibly distinct.
- Every final result has provenance.
- AI-generated content cannot directly mark execution as passed.
- Execution history cannot be rewritten.
- A report can be traced back to the exact workflow and script revisions used.

### 12.5 Timing history

- Each automated step records duration.
- The UI shows duration across multiple runs.
- Timing differences do not automatically fail the run in the MVP.

---

## 13. Explicit MVP non-goals

To prevent uncontrolled scope growth, do not include these in the first hybrid
release:

- full load, stress, soak, or concurrency testing;
- mobile-native application automation;
- desktop application automation;
- continuous video capture;
- AI autonomous sign-off;
- AI-generated final pass/fail decisions;
- automatic Git-diff impact analysis;
- IDE or VS Code integration;
- autonomous locator repair;
- visual pixel-diff approval as a final authority;
- arbitrary scripting inside workflow steps;
- complex branching and loops;
- cloud-scale parallel browser farms;
- shared authentication with PM-Again;
- two-way PM-Again data synchronization;
- replacing the existing manual execution mode.

Manual QA remains a first-class workflow, not a fallback.

---

## 14. Phase 2 candidates

These features are intentionally deferred until the MVP produces real usage
data.

### 14.1 Git and IDE impact analysis

Potential flow:

```text
Git diff or pull request
        ↓
Changed files and modules
        ↓
Mapped functions and business areas
        ↓
Suggested regression suites
        ↓
QA selects what to run
```

This requires a trustworthy traceability model connecting code, requirement,
feature, test case, and workflow. It should not be added as a shallow AI prompt
without that source-of-truth structure.

### 14.2 AI evidence assistant

Possible draft-only functions:

- propose crop;
- detect likely PDPA fields;
- propose blur regions;
- highlight changed areas;
- draft numbered callouts;
- summarize visible failure.

A human must review before saving a new annotation revision.

### 14.3 Requirement graph

Future traceability:

```text
Requirement
  → business rule
  → data rule
  → function/module
  → test case
  → workflow revision
  → execution run
  → evidence
  → defect
  → sign-off
```

This is the long-term foundation for defensible impact analysis.

### 14.4 Controlled performance thresholds

Allow project owners to set informational or blocking thresholds after enough
baseline history exists.

Threshold changes must be versioned and visible in reports.

### 14.5 Reusable workflow components

Examples:

- login component;
- project selection component;
- upload component;
- approval component;
- logout component.

Versioning and parameter ownership must be designed before implementation.

---

## 15. Delivery plan

The existing manual QA rebuild phases should remain the baseline. Do not destroy
working manual capabilities in order to introduce automation.

### Track A — Complete and stabilize current rebuild

Follow the current rebuild document through:

1. repository audit and ADR decisions;
2. deployment scaffold;
3. identity, projects, and roles;
4. test suites and immutable revisions;
5. test cycles and manual execution;
6. evidence capture and annotation;
7. dashboards, reports, and export;
8. hardening and handover.

### Track B — Hybrid expansion

#### HYB-0 — Architecture decisions and spike

Deliverables:

- ADR superseding the Playwright non-goal;
- local runner communication design;
- runner-token security design;
- Playwright recording spike;
- semantic locator evaluation;
- pause/resume browser-context spike;
- evidence-upload spike;
- Windows and macOS feasibility check.

Exit gate:

- a local runner opens a visible browser;
- executes three recorded steps;
- pauses for a human decision;
- resumes;
- uploads one screenshot;
- stores an auditable run record.

#### HYB-1 — Workflow model and editor

Deliverables:

- workflow definitions and revisions;
- workflow steps;
- draft/publish/clone behavior;
- test-case links;
- basic visual step editor;
- manual checkpoint editor.

#### HYB-2 — Runner registration and execution

Deliverables:

- runner registration and revocation;
- runner heartbeat;
- job claim protocol;
- execution state machine;
- Chromium execution;
- structured step results;
- failure categories.

#### HYB-3 — Recorder

Deliverables:

- record session creation;
- semantic locator capture;
- sensitive-input handling;
- draft workflow generation;
- locator warnings;
- tester review before publish.

#### HYB-4 — Hybrid checkpoint and evidence

Deliverables:

- pause/resume UI;
- manual decisions;
- screenshot capture/upload;
- annotation linkage;
- defect linkage;
- lost-runner handling.

#### HYB-5 — Timing, reports, and hardening

Deliverables:

- per-step timing history;
- hybrid execution report;
- machine-vs-human result provenance;
- export updates;
- threat model;
- recovery and retry rules;
- operator and tester guides.

---

## 16. Technical repository direction

Recommended repository shape if the runner lives in the same repository:

```text
qa-again/
├─ backend/                 FastAPI control plane
├─ frontend/                React/Vite web application
├─ runner/                  Node.js + Playwright local runner
│  ├─ src/
│  │  ├─ api/
│  │  ├─ browser/
│  │  ├─ execution/
│  │  ├─ recorder/
│  │  ├─ security/
│  │  └─ main.ts
│  ├─ package.json
│  └─ README.md
├─ docs/
│  ├─ adr/
│  ├─ HYBRID_RUNNER_PROTOCOL.md
│  ├─ HYBRID_RUNNER_THREAT_MODEL.md
│  └─ HYBRID_TESTER_GUIDE.md
└─ ...
```

Keep the runner versioned independently from the web release even if it is in
the same repository.

The backend remains Python/FastAPI. Do not rewrite the control plane in Node.js
merely because the runner uses Playwright.

---

## 17. Quality gates

### Backend

```bash
cd backend
ruff check .
pytest
```

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

### Runner

Final scripts should match the actual runner package, but the minimum gate is:

```bash
cd runner
npm run lint
npm run typecheck
npm test
npm run build
```

### End-to-end hybrid gate

A release is not complete until a real local runner proves:

```text
Create run
→ claim run
→ open browser
→ execute automation
→ pause at manual checkpoint
→ record human decision
→ upload evidence
→ resume automation
→ complete run
→ export traceable report
```

Do not accept mocked runner output as the final phase gate.

---

## 18. Product language

Recommended product category:

```text
Hybrid Evidence-First QA Platform
```

Recommended internal vision:

```text
QA-Again is a confidence management system for AI-accelerated software delivery.
```

Avoid presenting it as fully autonomous QA.

The differentiating value is the connection between:

- repeatable browser execution;
- human judgement;
- evidence;
- immutable history;
- trustworthy reporting.

---

## 19. Final principles

1. **Evidence before confidence.**
2. **Automation repeats; humans judge.**
3. **AI drafts; authorized users approve.**
4. **Published revisions never change in place.**
5. **A runner problem is not automatically a product failure.**
6. **Every result must disclose its provenance.**
7. **No pass without an executed assertion or human decision.**
8. **Performance history is shown before it is judged.**
9. **Manual testing remains fully supported.**
10. **Start with the SATL pain point before attempting IDE-level intelligence.**

The platform succeeds when the team no longer has to repeatedly perform and
re-document the same browser regression flow by hand, while still retaining a
human-verifiable record of what actually happened.

---

## 20. First instruction for the implementation team

Send the existing rebuild master prompt and this document together, then use the
following instruction:

```text
Treat QA_AGAIN_REBUILD_PROMPT_FASTAPI_REACT.md as the current application and
architecture baseline. Treat QA_AGAIN_HYBRID_AI_QA_MVP_EXPANSION.md as the
approved product-direction proposal for hybrid execution.

Before writing implementation code:

1. Read the existing QA-Again repository and PM-Again conventions required by
   the rebuild document.
2. Identify exactly what already exists for manual test execution, evidence,
   annotation, revisioning, audit, reports, and export.
3. Write ADR-HYB-001 that deliberately supersedes only the former “no
   Playwright E2E automation platform” non-goal.
4. Produce a gap analysis against sections 4–13 of the hybrid expansion.
5. Propose the smallest HYB-0 technical spike using a local Node.js Playwright
   runner and the existing FastAPI control plane.
6. Do not begin the full feature build until the spike proves visible-browser
   execution, manual pause/resume, evidence upload, and auditable result
   provenance.
7. Preserve all existing manual QA capabilities and immutable evidence rules.
8. Do not report success from mocks alone. Demonstrate the complete hybrid gate
   with a real browser.
```
