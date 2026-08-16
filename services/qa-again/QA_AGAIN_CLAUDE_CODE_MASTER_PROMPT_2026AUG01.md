# QA-Again — Claude Code Master Implementation Prompt

Repository: `https://github.com/gunaex/QA-Again`

## Your role

Act as the principal engineer, solution architect, security reviewer, QA lead, and technical writer for **QA-Again**.

Your job is to inspect the existing repository first, preserve useful existing work, and then implement a production-shaped MVP in controlled phases. Do not blindly replace the repository, do not rewrite working code without reason, and do not assume the repository is empty.

Work directly in the repository. Make real code changes, run the tests, run the Cloudflare-compatible preview, keep the working tree clean, and produce a clear handover.

Do not stop after writing a plan. Continue implementation phase by phase unless a real blocking dependency requires user action, such as creating Cloudflare resources or supplying account IDs/secrets. Where manual Cloudflare setup is required, implement everything possible locally and document the exact commands and dashboard steps.

---

# 1. Product vision

Build **QA-Again** as a standalone, reusable quality-assurance application.

QA-Again must remain separate from **PM-Again**. The two applications must not share source code, runtime state, or databases. PM-Again only links users to a QA-Again project. QA-Again may provide a link back to the matching PM-Again project.

The primary purpose of QA-Again is to solve the largest operational problem in manual QA: **evidence capture, annotation, traceability, revision history, and customer-ready reporting**.

The application must support multiple independent projects. Each project contains its own members, roles, test scripts, revisions, test cycles, execution results, evidence, defects, reports, and settings.

The product must be generic. Do not hard-code SATL, Material, Vendor, Resin, HF, PT, or any other project-specific terminology into the database schema or core business logic. SATL is an import fixture and a real usage example, not the product model.

---

# 2. Non-negotiable decisions

These are already decided. Do not reopen them without a genuine technical blocker.

1. **QA-Again is a separate application from PM-Again.**
2. **Cloudflare is the only infrastructure provider.**
3. Do not use Vercel, Supabase, Firebase, AWS S3, external databases, or external file-storage services.
4. Use:
   - Cloudflare Workers for the deployed web application/API;
   - Cloudflare D1 for relational data and metadata;
   - Cloudflare R2 for imported source files and screenshot evidence;
   - Cloudflare Access for authentication at the application perimeter;
   - D1 project membership for application authorization.
5. **No video recording, no video upload, and no video evidence.**
6. Evidence supports screenshots and image files only for the MVP.
7. Use open-source embedded components where suitable instead of building every editor/export feature from scratch.
8. The visual identity is:
   - green as the main product color;
   - light orange for NG/FAIL states and evidence annotations;
   - red only for deletion, security/data-corruption danger, or severe P0 blocker warnings.
9. Excel export is mandatory.
10. In-app reports are mandatory.
11. Printable report/PDF support should use print-optimized HTML and the browser Print-to-PDF workflow for the MVP. Do not add a heavy server-side PDF renderer.
12. The design must fit Cloudflare free-plan constraints and must fail clearly when a quota/limit is reached.

---

# 3. First action: inspect the repository

Before changing code, inspect and document the current repository.

Run and report at least:

```bash
pwd
git status --short --branch
git log --oneline --decorate -20 || true
find . -maxdepth 3 -type f \
  -not -path './.git/*' \
  -not -path './node_modules/*' \
  | sort
```

Inspect:

- README and documentation;
- package manager and lockfile;
- framework and runtime;
- TypeScript configuration;
- current routes and components;
- current authentication code;
- database/ORM code;
- Cloudflare configuration;
- tests and CI;
- lint/build scripts;
- current UI design system;
- existing license.

Create:

```text
docs/REPOSITORY_AUDIT.md
```

The audit must contain:

- current architecture;
- useful existing components to retain;
- missing requirements;
- technical risks;
- dependency/license concerns;
- proposed migration path;
- whether the existing framework can deploy cleanly to Cloudflare Workers;
- exact recommended phase plan.

Do not replace the existing framework merely because another stack is preferred. Preserve it if it is viable on Cloudflare Workers. If the repository is genuinely empty or only contains a placeholder, use the fallback stack in the next section.

Commit the audit before major implementation:

```text
chore: audit QA-Again repository and establish implementation plan
```

---

# 4. Fallback stack when the repository has no usable scaffold

Use this only if the repository does not already contain a viable application stack.

- Next.js App Router
- TypeScript strict mode
- Cloudflare Workers via `@opennextjs/cloudflare`
- Wrangler
- D1
- R2
- Drizzle ORM with SQLite/D1-compatible migrations, unless the existing repository already uses a suitable D1-compatible data layer
- Tailwind CSS or the repository’s existing styling system
- Zod for request/import validation
- Vitest for unit/integration tests
- Playwright for critical browser flows
- `remark`/`unified` ecosystem for deterministic Markdown parsing where beneficial
- SheetJS Community or ExcelJS for input parsing, selected after testing browser and Worker compatibility
- ExcelJS for browser-side `.xlsx` export if it passes the compatibility spike
- JSZip for the portable evidence package

Use the repository’s existing package manager. Do not create a second lockfile.

Cloudflare deployment must use the current official adapter/configuration rather than old Pages-only patterns.

Required scripts should be conceptually equivalent to:

```json
{
  "dev": "next dev",
  "preview": "opennextjs-cloudflare build && opennextjs-cloudflare preview",
  "deploy": "opennextjs-cloudflare build && opennextjs-cloudflare deploy",
  "cf-typegen": "wrangler types",
  "lint": "...",
  "typecheck": "...",
  "test": "...",
  "test:e2e": "...",
  "build": "..."
}
```

Use a current compatibility date and `nodejs_compat` only where required by the Cloudflare adapter. Do not copy stale values without checking the current documentation and package versions.

---

# 5. Required high-level architecture

```text
PM-Again                          QA-Again
separate repository              this repository
separate deployment              Cloudflare Worker
separate data                    D1 database
     │                            R2 private bucket
     │ Open QA Again link              │
     └─────────────────────────────────►
                                  Cloudflare Access
                                  project authorization in D1
```

## Separation rules

- Do not import PM-Again source code into QA-Again.
- Do not connect directly to the PM-Again database.
- Do not make QA-Again depend on PM-Again availability.
- QA-Again projects may store an optional external PM reference:
  - `external_system = PM_AGAIN`
  - `external_project_id`
  - `external_project_code`
  - `external_project_url`
- Display `Back to PM-Again` only when a valid external URL exists.
- PM-Again can link to the QA project’s stable URL.
- Do not implement unauthenticated automatic project provisioning from query parameters.
- If an automatic provisioning API is added later, it must use signed service-to-service authentication and idempotency. For the MVP, manual project creation plus external-link configuration is acceptable and safer.

---

# 6. Cloudflare resource model

Use environment-specific bindings and never hard-code account-specific identifiers.

Suggested bindings:

```text
DB                  D1 database
QA_EVIDENCE         private R2 bucket
ASSETS              Worker static assets binding when required by the framework
```

Suggested non-secret variables:

```text
APP_NAME=QA-Again
APP_ENV=local|preview|production
PUBLIC_APP_URL=...
ACCESS_TEAM_DOMAIN=...
ACCESS_AUD=...
MAX_EVIDENCE_BYTES=5242880
MAX_EVIDENCE_WIDTH=1920
DEFAULT_PROJECT_QUOTA_BYTES=1073741824
```

Suggested secrets:

```text
# Only if needed by the final Access verification approach.
# Never commit secret values.
```

Create:

```text
wrangler.jsonc or wrangler.toml
.env.example
.dev.vars.example
docs/CLOUDFLARE_SETUP.md
docs/DEPLOYMENT.md
```

Document exact commands for:

- creating D1;
- applying local migrations;
- applying remote migrations;
- creating the private R2 bucket;
- configuring bindings;
- configuring Cloudflare Access;
- configuring local developer authentication;
- previewing with the Worker/workerd runtime;
- deploying;
- rolling back to a previous Worker version;
- D1 backup/Time Travel procedure available on the active plan;
- monitoring free-plan usage.

Do not claim a resource is free forever. Document current limits as operational assumptions and link to official Cloudflare documentation in the handover.

---

# 7. Authentication and authorization

## Authentication

Production must be protected by Cloudflare Access.

Support these Access identity options in the setup documentation:

- Cloudflare identity provider for internal account users;
- One-time PIN for approved guest/customer email addresses when needed;
- an external identity provider later without changing application authorization.

Do not build a password database in QA-Again.

The application must validate the Cloudflare Access JWT before trusting identity claims. Do not trust a client-supplied email header on an unprotected route.

Normalize user email using a clear rule such as trimmed lowercase for membership matching, while preserving the display value when available.

Upsert the authenticated user profile on access:

```text
users
- id
- email_normalized UNIQUE
- email_display
- display_name nullable
- avatar_url nullable
- first_seen_at
- last_seen_at
- status
```

## Local development

Provide a clearly isolated local development identity mechanism.

Requirements:

- enabled only when `APP_ENV=local` and an explicit local flag is present;
- impossible to enable accidentally in production;
- visual development banner identifying the mock user;
- documented test users for Admin, Tester, and Viewer;
- fail closed when production Access identity is missing or invalid.

## Authorization

Cloudflare Access answers “who is this user?”

D1 answers “what may this user do in this project?”

Project roles:

```text
ADMIN
TESTER
VIEWER
```

A user may have a different role in each project.

Minimum permission contract:

### ADMIN

- create/edit/archive QA project;
- manage project members;
- configure external PM link;
- import test scripts;
- create/clone/edit/publish script revisions;
- create test cycles;
- assign testers;
- execute tests;
- review results;
- approve NOT APPLICABLE;
- lock/unlock according to controlled policy;
- manage project storage policy;
- export reports and evidence packages.

### TESTER

- view assigned/accessible scripts and cycles;
- execute test cases;
- enter actual result;
- set PASS, NG/FAIL, BLOCKED, or NOT RUN according to workflow;
- attach/capture/paste evidence;
- annotate evidence;
- create/link defects;
- retest;
- export only where project policy allows.

### VIEWER

- read project data;
- view script revisions, cycles, results, evidence, and reports;
- download approved exports where permitted;
- cannot mutate project/test/evidence data.

Every API mutation must authorize on the server. Hiding a button is not authorization.

Add tests proving cross-project access is denied.

---

# 8. Product information architecture and routes

Implement a clean project-scoped structure.

Suggested routes:

```text
/
/projects
/projects/new
/projects/[projectSlug]
/projects/[projectSlug]/dashboard
/projects/[projectSlug]/scripts
/projects/[projectSlug]/scripts/import
/projects/[projectSlug]/scripts/[suiteId]
/projects/[projectSlug]/scripts/[suiteId]/revisions/[revisionId]
/projects/[projectSlug]/cycles
/projects/[projectSlug]/cycles/new
/projects/[projectSlug]/cycles/[cycleId]
/projects/[projectSlug]/cycles/[cycleId]/execute
/projects/[projectSlug]/cycles/[cycleId]/cases/[resultId]
/projects/[projectSlug]/evidence
/projects/[projectSlug]/defects
/projects/[projectSlug]/reports
/projects/[projectSlug]/members
/projects/[projectSlug]/settings
```

Navigation within a QA project:

```text
Dashboard
Test Scripts
Test Cycles
Execute
Evidence
Defects
Reports
Members
Settings
```

The project list should be independent of PM-Again but may visually feel related. Do not clone PM-Again exactly. QA-Again needs its own green evidence-focused identity.

---

# 9. UI theme and design system

Use accessible tokens rather than scattered hard-coded colors.

Suggested base tokens:

```text
Primary green:          #2E7D32
Primary hover:          #256428
Primary soft:           #EAF6EC
Primary border:         #B8DDBF
PASS background:        #E8F5E9

NG soft background:     #FFF4E5
NG border:              #F6C47A
NG text:                #9A5200
NG action:              #E98A15
Annotation highlight:   #FFB74D

Blocked background:     light yellow
Not-run background:     neutral gray
N/A background:         blue-gray
Danger red:             deletion/security/P0 destructive warning only
```

Status wording in the UI:

- `PASS`
- `NG` with a secondary explanatory label `Fail` where useful
- `BLOCKED`
- `NOT RUN`
- `NOT APPLICABLE`

Do not make ordinary NG cards bright red.

Required UX qualities:

- desktop-first but responsive;
- keyboard-accessible controls;
- clear focus states;
- WCAG-readable text contrast;
- no color-only meaning;
- confirmation for destructive actions;
- clear empty/loading/error states;
- sticky execution actions where helpful;
- autosave draft actual-result text with explicit saved state;
- no hidden silent failures.

---

# 10. Core domain model

Use stable IDs, timestamps, actor IDs, and project scoping throughout.

The exact SQL may be adapted to the existing repository, but the semantics must be preserved.

## Projects and members

```text
qa_projects
- id
- project_code
- slug UNIQUE
- name
- description
- status ACTIVE|ARCHIVED
- external_system nullable
- external_project_id nullable
- external_project_code nullable
- external_project_url nullable
- target_app_url nullable
- default_environment nullable
- storage_quota_bytes
- created_by
- created_at
- updated_at
- archived_at nullable

project_members
- id
- project_id
- user_id
- role ADMIN|TESTER|VIEWER
- status ACTIVE|INVITED|DISABLED
- added_by
- added_at
- updated_at
- UNIQUE(project_id, user_id)
```

## Test scripts and revisions

```text
test_suites
- id
- project_id
- suite_code nullable
- name
- description
- suite_type REGRESSION|UAT|SMOKE|INTEGRATION|OTHER
- status ACTIVE|ARCHIVED
- created_by
- created_at
- updated_at

script_revisions
- id
- project_id
- suite_id
- revision_label
- revision_number_sort
- status DRAFT|PUBLISHED|SUPERSEDED|ARCHIVED
- change_summary
- source_type MARKDOWN|XLSX|CSV|CLONE|MANUAL
- source_object_key nullable
- source_filename nullable
- source_sha256 nullable
- imported_at nullable
- imported_by nullable
- published_at nullable
- published_by nullable
- supersedes_revision_id nullable
- created_at
- updated_at
- UNIQUE(suite_id, revision_label)
```

Published revisions are immutable.

A correction must clone the revision into a new DRAFT revision. Do not edit published content in place.

## Test cases

```text
test_cases
- id
- project_id
- suite_id
- revision_id
- logical_case_key
- checkpoint_code
- title
- category nullable
- priority nullable
- traceability_json
- fixture_md nullable
- environment_md nullable
- setup_md nullable
- action_md
- validation_md nullable
- expected_result_md
- negative_path boolean
- mutation_level READ_ONLY|MUTATING|MIXED|UNSPECIFIED
- sequence_no
- source_location_json nullable
- content_sha256
- created_at
- UNIQUE(revision_id, checkpoint_code)
```

Use `logical_case_key`/`checkpoint_code` for revision comparison, but do not assume a key is globally unique across all projects.

## Test cycles and results

```text
test_cycles
- id
- project_id
- suite_id
- script_revision_id
- cycle_code nullable
- name
- environment
- release_version nullable
- git_commit nullable
- image_digest nullable
- target_base_url nullable
- status DRAFT|READY|IN_PROGRESS|REVIEW|COMPLETED|LOCKED|CANCELLED
- started_at nullable
- finished_at nullable
- created_by
- created_at
- updated_at
- locked_at nullable
- locked_by nullable

cycle_test_results
- id
- project_id
- cycle_id
- test_case_id
- assigned_tester_id nullable
- status NOT_RUN|PASS|FAIL|BLOCKED|NOT_APPLICABLE
- actual_result_md nullable
- blocked_reason nullable
- na_reason nullable
- defect_reference nullable
- started_at nullable
- executed_at nullable
- executed_by nullable
- reviewed_at nullable
- reviewed_by nullable
- review_status UNREVIEWED|ACCEPTED|CHANGES_REQUESTED
- result_revision_no
- created_at
- updated_at
- UNIQUE(cycle_id, test_case_id)
```

A cycle must reference one exact published script revision. Publishing a later script revision must never change an existing cycle.

Once a cycle is LOCKED:

- ordinary result/evidence mutation is blocked;
- exports remain available;
- any administrative reopen must require reason and append an audit record;
- historical results must not be silently rewritten.

## Evidence

```text
evidence_items
- id
- project_id
- cycle_id
- test_result_id
- evidence_code
- evidence_type SCREENSHOT|UPLOADED_IMAGE|PASTED_IMAGE
- original_object_key
- original_filename
- original_content_type
- original_size_bytes
- original_width
- original_height
- original_sha256
- thumbnail_object_key nullable
- current_revision_no
- caption nullable
- target_url nullable
- target_page_title nullable
- browser_metadata_json nullable
- captured_at
- captured_by
- status ACTIVE|ARCHIVED
- created_at

 evidence_revisions
- id
- evidence_id
- revision_no
- annotation_object_key
- annotation_sha256
- rendered_object_key nullable
- rendered_sha256 nullable
- change_summary nullable
- created_by
- created_at
- UNIQUE(evidence_id, revision_no)
```

Keep the original screenshot immutable.

Store annotation/design-state JSON separately from the original.

Do not permanently store a full rendered image for every annotation revision unless the implementation proves it is necessary. Prefer rendering for preview/export and optionally cache the current thumbnail/final preview.

## Defects, sign-off, and audit

```text
defects
- id
- project_id
- cycle_id nullable
- test_result_id nullable
- defect_key
- title
- description_md nullable
- severity P0|P1|P2|P3|UNSPECIFIED
- status OPEN|IN_PROGRESS|FIXED|RETEST|CLOSED|REJECTED
- external_url nullable
- created_by
- created_at
- updated_at

sign_offs
- id
- project_id
- cycle_id
- signoff_type QA_REVIEW|BUSINESS_ACCEPTANCE|GO_LIVE
- decision APPROVED|REJECTED|PENDING
- comment_md nullable
- actor_id
- acted_at

audit_logs
- id
- project_id nullable
- actor_id nullable
- action
- entity_type
- entity_id
- before_json nullable
- after_json nullable
- reason nullable
- created_at
```

Audit logs are append-only from the application’s perspective.

Create indexes for common project, cycle, revision, status, and checkpoint filters. Avoid full-table scans because D1 usage is based partly on rows read.

---

# 11. Test script import and revision management

## Required input formats

MVP must support:

1. Markdown `.md`
2. Excel `.xlsx`
3. CSV `.csv`
4. Clone from an existing revision

Manual authoring may be basic in the MVP; reliable import is more important.

## Import workflow

```text
Select project and test suite
    ↓
Upload source file
    ↓
Store immutable original source in R2
    ↓
Calculate SHA-256
    ↓
Parse into a temporary preview model
    ↓
Show mapping and warnings
    ↓
Validate duplicates and required fields
    ↓
Create DRAFT revision
    ↓
Admin review
    ↓
Publish immutable revision
```

Never create a published revision directly from an unreviewed import.

## Markdown importer requirements

Use this real source document as a required fixture when it is available in the workspace:

```text
SATL_REGRESSION_CHECKPOINT_SCRIPT_PRE_GOLIVE_2026AUG01.md
```

Copy the fixture into an appropriate non-secret test-fixtures directory if the user provides it to the repository. Do not invent missing source content.

The importer must support the structure used by this document:

- document H1 title;
- document metadata such as date, system, URL, audience, and document type;
- status-definition tables;
- warnings and blocker tables;
- detailed test cases whose headings look like:
  - `### REG-P0-001 — ...`
  - `### MASTER-P0-001 — ...`
- optional bold metadata such as:
  - `**Traceability:**`
  - `**Fixture:**`
  - `**Fixtures:**`
  - `**Environment:**`
  - `**Setup:**`
  - `**Action:**`
  - `**Validate:**`
  - `**Expected:**`
  - `**Expected for currently fixed behavior**`
  - `**Additional P0 requirement not yet accepted**`
- numbered and bulleted action steps;
- multiline expected results;
- historical traceability matrix;
- release gates;
- execution result template;
- handover instructions.

### Important import rule for the SATL source

The detailed checkpoints in the P0 sections are primary test cases.

The later historical fixed-issue regression matrix is a traceability index and must **not create duplicate test cases by default** when its references already map to detailed cases. Preserve the matrix as source metadata or an optional secondary import mode.

The importer must distinguish:

- currently fixed expected behavior;
- additional P0 requirements not yet accepted;
- release blockers;
- read-only Production smoke;
- UAT/isolation mutation tests.

Do not relabel pending P0 requirements as completed or fixed.

Expected status definitions from the source must be preserved:

```text
PASS
FAIL
BLOCKED
NOT RUN
NOT APPLICABLE
```

In the UI, FAIL may be displayed primarily as `NG`, but the canonical stored value remains `FAIL` for interoperability and reporting.

### Import preview

Show:

- detected cases;
- duplicate checkpoint IDs;
- missing title/action/expected result;
- source lines/section where possible;
- warnings;
- parsed traceability;
- whether a case is mutating or read-only when detectable;
- fields that require user mapping;
- cases skipped and reason.

Do not silently discard content.

## Excel/CSV importer

Support a standard mapping template with at least:

```text
Test ID
Title
Priority
Traceability
Fixture
Environment
Preconditions / Setup
Test Steps / Action
Validation
Expected Result
Negative Path
Mutation Level
```

Allow the user to map uploaded column names to canonical fields in the preview step.

Reject or warn on duplicate IDs within the same revision.

## Revision comparison

Provide comparison between two revisions in the same suite:

```text
Added
Changed
Removed
Unchanged
```

Compare primarily by checkpoint/logical case key and content hash.

For changed cases, show a readable field-level diff for:

- title;
- setup;
- action;
- validation;
- expected result;
- traceability;
- priority.

Removed cases remain visible in revision history. Do not hard-delete historical cases.

---

# 12. Test cycle and execution workflow

## Cycle creation

An Admin selects:

- project;
- suite;
- one PUBLISHED script revision;
- cycle name;
- environment;
- release/version metadata;
- target application URL;
- optional assigned testers.

Creating a cycle creates one result row for each case in the chosen revision with status `NOT_RUN`.

## Execution screen

Build an evidence-first execution UI.

Recommended layout:

```text
Left panel
- case list
- filters
- status and assignee
- progress

Main panel
- checkpoint ID and title
- traceability/fixture/environment
- setup
- actions
- validation
- expected result
- actual result editor
- evidence gallery
- defect link

Sticky action area
- Save draft
- PASS
- NG
- BLOCKED
- NOT APPLICABLE (policy controlled)
- Next case
```

Required behavior:

- Tester can move between cases without losing draft text.
- Actual result supports Markdown/plain text safely.
- PASS must be blocked when the project/cycle evidence policy requires evidence and none exists.
- NG must require an actual result or NG reason.
- BLOCKED must require a blocked reason.
- NOT APPLICABLE must require a written reason and Admin approval/review.
- A result cannot appear completed while an evidence upload is still pending or failed.
- Show unsaved/saving/saved/error states clearly.
- Do not allow a result to mutate after the cycle is locked.

## Result history

Do not destroy the prior result silently when status or actual result changes.

At minimum, append an audit record containing before/after values and increment `result_revision_no`.

Show a result activity/history panel.

---

# 13. Target application launch and screenshot capture

The user wants to open the application under test from QA-Again and capture evidence without a video system.

Implement these modes:

## A. Open target application

- Project/cycle stores a target URL.
- Provide `Open Target App` in a new tab/window.
- Preserve the current test case context in QA-Again.
- Optionally support an embedded iframe preview only when the target allows framing.
- Do not make iframe embedding the default or a dependency.
- Clearly explain when cross-origin/browser security prevents embedding.

## B. Capture tab/window/screen as a single screenshot

Use the browser Screen Capture API where supported:

1. User clicks `Capture Evidence`.
2. Browser asks the user to select a tab, window, or screen.
3. Acquire the media stream.
4. Draw one frame to a canvas.
5. Stop all tracks immediately.
6. Do not retain or upload video data.
7. Open the screenshot in the annotation flow.

The source code and UI must make it clear this is single-frame capture, not recording.

## C. Paste screenshot

Support clipboard image paste:

```text
Ctrl+V
Command+V
```

Paste must work inside a clearly identified evidence drop zone and must not unexpectedly intercept paste in text fields.

## D. Upload/drag-and-drop

Support PNG, JPEG, and WebP for the MVP.

Validate actual MIME signatures where practical; do not trust only the extension.

Reject unsupported files with a clear message.

## No video

Do not implement:

- MediaRecorder;
- video upload;
- video playback;
- persistent media streams;
- Playwright video recording;
- video evidence database fields.

---

# 14. Evidence annotation: embed open-source capability

Do not build a full image editor from zero.

Perform a short compatibility spike and select a permissively licensed open-source component.

Preferred candidate:

```text
Filerobot Image Editor
```

Reasons to evaluate:

- React integration;
- crop;
- drawing;
- text;
- arrows/lines;
- undo/redo;
- design-state export and reload;
- MIT license.

Mandatory fallback if the preferred component is incompatible with the repository’s React version, Cloudflare bundle, or product UX:

```text
react-konva + Konva
```

Do not silently force incompatible peer dependencies.

Create an ADR:

```text
docs/adr/ADR-001-evidence-annotation-component.md
```

The ADR must document:

- evaluated libraries;
- license;
- current maintenance state;
- React/framework compatibility;
- bundle impact;
- selected approach;
- fallback approach;
- what small QA-specific wrapper code is still required.

Create/update:

```text
THIRD_PARTY_NOTICES.md
```

Do not embed AGPL/SSPL/proprietary code unless explicitly approved.

## Required annotation functions

- highlight rectangle;
- arrow/line;
- text annotation;
- crop;
- blur or pixelation for sensitive information if supported safely;
- undo/redo;
- zoom/pan where practical;
- reset to original;
- save design state;
- reopen and continue editing;
- orange default annotation style;
- original/annotated preview toggle.

## Numbered callouts

Implement a lightweight QA-specific callout layer around the embedded editor:

- numbered callouts `1`, `2`, `3`, ...;
- each callout has description;
- optional Expected/Actual fields;
- callout order is stable;
- callout descriptions are included in Excel/report export.

Do not fork or rewrite the complete editor merely to add callouts. Keep the custom layer small and isolated.

## Evidence integrity

On upload/capture:

- resize/compress in the browser before upload;
- maximum width default 1920 px;
- convert to WebP when supported and visually acceptable;
- preserve original dimensions/metadata in D1;
- calculate SHA-256 in the browser or Worker;
- enforce 5 MB maximum after processing by default;
- deduplicate identical originals within the same result/project where safe;
- store the original once;
- store annotation revisions separately;
- never mutate the original object.

Do not store secrets, session cookies, tokens, or signed URLs in evidence metadata.

Allow the tester to blur sensitive information before an annotated copy is included in customer export. Keep access to the immutable original restricted by project permissions.

---

# 15. R2 evidence storage design

Use a private bucket.

Suggested object layout:

```text
projects/{projectId}/
  imports/{suiteId}/{revisionId}/source/{sha256}-{safeFilename}
  cycles/{cycleId}/
    cases/{testResultId}/
      evidence/{evidenceId}/
        original/{sha256}.webp
        thumbnail/current.webp
        annotations/rev-0001.json
        annotations/rev-0002.json
        rendered/current.webp        # optional cache only
```

Do not expose the bucket publicly.

For the MVP, prefer an authenticated Worker upload endpoint using an R2 binding and streaming where possible. Enforce a small image limit and avoid buffering unnecessary copies.

Only introduce S3-compatible presigned uploads if measurements show that the Worker upload path is insufficient. If presigned upload is added, keep credentials server-side and document the security model.

Evidence download/preview routes must:

- authorize project access;
- use short-lived controlled responses or stream through an authorized Worker route;
- set correct content type;
- set safe content-disposition;
- prevent object-key traversal;
- avoid leaking private R2 object keys unnecessarily.

## Storage quota

Implement per-project accounting:

- current evidence bytes;
- imported source bytes;
- configured quota;
- usage percentage;
- warnings at 70%, 85%, and 95%;
- hard stop at 100% unless Admin changes policy;
- explain that provider-level Cloudflare limits may also apply.

No hard delete from a locked cycle.

Archiving evidence must preserve auditability. If deletion is supported for unlocked draft evidence, require Admin authorization and audit it.

---

# 16. Dashboard and reports

## Project QA dashboard

Show at least:

- total test cases in active cycle;
- PASS count;
- NG count;
- BLOCKED count;
- NOT RUN count;
- NOT APPLICABLE count;
- pass rate with denominator clearly defined;
- evidence completeness percentage;
- open defects by severity;
- current cycle progress;
- pending reviews;
- P0/go-live blockers;
- storage usage;
- recent activity.

Do not count NOT RUN as PASS. Make formulas explicit in tooltips.

## Reports in the app

Implement filters by:

- project;
- suite;
- script revision;
- cycle;
- environment;
- release version;
- status;
- tester;
- checkpoint ID;
- traceability;
- defect;
- date range.

Required reports:

1. Execution Summary
2. Detailed Test Result
3. NG and Defect Report
4. Evidence Completeness
5. Revision Comparison
6. Cycle-to-Cycle Comparison
7. Tester Progress
8. Go-Live Readiness
9. Audit/Sign-off Summary
10. Project Storage Usage

## Cycle comparison

Example transitions:

```text
NG → PASS
NG → NG
BLOCKED → PASS
PASS → NG
NOT RUN → PASS
```

Comparison must use stable checkpoint/logical case keys and clearly mark cases that differ because the cycles reference different script revisions.

## Print report

Create print-optimized report pages with:

- cover/header;
- project and cycle metadata;
- summary;
- result matrix;
- NG details;
- selected annotated evidence;
- defect references;
- revision information;
- reviewer/sign-off;
- page-break control;
- print-safe colors.

Use browser Print-to-PDF for the MVP. Do not render PDF in the Worker.

---

# 17. Excel export and portable evidence package

Excel export is mandatory and should be generated in the browser or a browser Web Worker to avoid heavy Worker CPU usage.

Evaluate ExcelJS first and verify the generated workbook in Microsoft Excel-compatible format. If the existing repo already has a proven export library, retain it.

## Required workbook

Suggested sheets:

```text
00_Cover
01_Execution_Summary
02_Test_Results
03_NG_Defects
04_Evidence_Index
05_Revision_History
06_Sign_Off
```

### 00_Cover

Include:

- application/project;
- suite;
- script revision;
- cycle;
- environment;
- release version;
- target URL;
- execution period;
- generated by;
- generated timestamp/timezone;
- report version.

### 01_Execution_Summary

Include counts and definitions for all statuses and evidence completeness.

### 02_Test_Results

Columns at minimum:

```text
Sequence
Test ID
Title
Priority
Traceability
Fixture
Environment
Setup
Action
Validation
Expected Result
Actual Result
Status
Tester
Executed Date
Reviewer
Review Status
Defect ID
Evidence Count
Evidence Reference
```

### 03_NG_Defects

Include every NG case, severity, defect status, actual result, callout descriptions, and evidence reference.

### 04_Evidence_Index

Include:

- Evidence ID;
- Test ID;
- caption;
- captured by/date;
- original hash;
- annotation revision;
- callout summary;
- thumbnail where practical;
- link/reference within the portable package.

Do not place huge full-resolution images into every row. Use constrained thumbnails and provide the full annotated images in the ZIP package.

### 05_Revision_History

Include source filename/hash, revision label, status, change summary, publish actor/date, and comparison summary.

### 06_Sign_Off

Include reviewer/business decision, actor, timestamp, and comments.

## Export modes

### Customer Excel

- `.xlsx`
- compact thumbnails;
- no internal secrets;
- customer-safe annotated evidence only.

### Portable Evidence Package

Generate client-side ZIP:

```text
{project}_{cycle}_evidence_package.zip
├── {project}_{cycle}.xlsx
├── report.html
├── evidence/
│   ├── {testId}_{evidenceCode}.webp
│   └── ...
└── manifest.json
```

The manifest must include hashes and references.

Do not persist generated Excel/ZIP reports in R2 by default. Generate and download them on demand to preserve free storage.

## Export correctness

Add automated tests for:

- required sheet names;
- row counts;
- checkpoint IDs;
- status values;
- line breaks;
- Unicode/Thai text;
- dates/timezones;
- evidence references;
- formula or summary totals;
- workbook opening without corruption.

---

# 18. Free-plan operational guardrails

Design for low request/CPU/storage usage.

Requirements:

- static-first rendering where practical;
- indexed D1 queries;
- pagination for large lists;
- no unbounded `SELECT *` on large tables;
- batch D1 writes during import/cycle creation;
- client-side image resize/compression;
- client-side Excel/ZIP generation;
- no server-side image rendering for every page load;
- lazy-load annotation editor and export libraries;
- no video;
- no public R2 listing;
- no permanent generated report copies by default;
- avoid giant Worker bundles;
- measure compressed Worker bundle size;
- use dynamic imports for heavy browser-only modules;
- record D1/R2 usage in an Admin diagnostics page where feasible.

Create:

```text
docs/FREE_PLAN_CAPACITY.md
```

Include:

- current official Workers/D1/R2/Access assumptions;
- estimated storage per screenshot after compression;
- example project capacity;
- expected failure behavior when limits are exceeded;
- upgrade path without redesign;
- features intentionally excluded to remain within free limits.

The app must show friendly errors for:

- D1 operation/limit failure;
- R2 upload/storage failure;
- Worker request failure;
- invalid Access session;
- export memory failure;
- unsupported capture browser.

Do not claim “unlimited.”

---

# 19. Security and data safety

Implement and test:

- server-side project authorization on all reads/writes;
- Access JWT verification;
- secure, normalized membership matching;
- CSRF-safe mutation approach appropriate to the chosen framework;
- input validation using schemas;
- safe Markdown rendering without arbitrary HTML/script execution;
- filename sanitization;
- object-key sanitization;
- MIME/type checks;
- upload size limits;
- private R2;
- no secret logging;
- no live signed URL in evidence/audit exports;
- immutable published revision semantics;
- immutable evidence original;
- locked-cycle enforcement;
- append-only audit behavior;
- safe archive instead of destructive delete for historical records;
- rate limiting or reasonable abuse guard on upload/import endpoints;
- no authorization based only on client UI state.

Add a basic threat model:

```text
docs/THREAT_MODEL.md
```

Cover:

- cross-project access;
- forged identity headers;
- malicious upload;
- stored XSS in Markdown/callouts;
- unauthorized evidence download;
- object-key guessing;
- accidental publication of sensitive screenshots;
- tampering with published revisions;
- tampering with locked results;
- customer export leakage.

---

# 20. Testing strategy

## Unit tests

Cover:

- role permission matrix;
- project scope guards;
- status transition rules;
- revision immutability;
- cycle lock rules;
- pass/evidence policy;
- checksum and safe object-key generation;
- Markdown parsing;
- Excel/CSV mapping;
- revision comparison;
- dashboard calculations;
- storage quota calculations;
- report filters.

## Integration tests

Use local D1/R2-compatible development tools where possible.

Cover:

- migrations;
- project/member CRUD authorization;
- import creates DRAFT revision;
- publish locks revision;
- cycle snapshots published revision;
- evidence upload metadata and R2 object;
- evidence annotation revision;
- locked cycle blocks mutation;
- audit rows created;
- cross-project access denied.

## E2E tests

Critical flows:

1. Admin creates project.
2. Admin adds Tester and Viewer.
3. Admin imports Markdown fixture.
4. Admin reviews and publishes revision.
5. Admin creates cycle.
6. Tester executes a case.
7. Tester pastes/uploads screenshot.
8. Tester annotates and adds callout.
9. Tester marks PASS or NG according to policy.
10. Viewer can view but cannot edit.
11. Admin views report.
12. Admin exports Excel.
13. Admin locks cycle.
14. Mutation is rejected after lock.
15. Back-to-PM link appears only when configured.

Do not enable Playwright video recording. Screenshots on test failure are allowed.

## Required quality gates

Before each phase is considered complete:

```bash
lint
typecheck
unit tests
integration tests where applicable
production build
Cloudflare preview/workerd smoke
```

The final handover must include actual results, not claims.

---

# 21. Observability and diagnostics

Keep logging useful but privacy-safe.

- structured logs;
- request/correlation ID;
- actor ID/email hash where appropriate, not secrets;
- entity/action/result;
- upload/import/export failures;
- no evidence binary or sensitive text in logs;
- diagnostics page for Admin with app version, deployment metadata, D1/R2 binding health, and recent safe errors;
- `/api/health` or equivalent showing application and binding readiness without exposing secrets.

Include immutable build metadata where practical:

```text
Git commit
Build timestamp
Environment
Worker version/deployment ID when available
```

---

# 22. Documentation deliverables

Maintain at least:

```text
README.md
docs/REPOSITORY_AUDIT.md
docs/ARCHITECTURE.md
docs/DATA_MODEL.md
docs/CLOUDFLARE_SETUP.md
docs/DEPLOYMENT.md
docs/AUTH_AND_ROLES.md
docs/TEST_SCRIPT_IMPORT.md
docs/EVIDENCE_MODEL.md
docs/EXCEL_EXPORT.md
docs/FREE_PLAN_CAPACITY.md
docs/THREAT_MODEL.md
docs/PM_AGAIN_INTEGRATION.md
docs/OPERATIONS_RUNBOOK.md
docs/USER_GUIDE_ADMIN.md
docs/USER_GUIDE_TESTER.md
docs/USER_GUIDE_VIEWER.md
THIRD_PARTY_NOTICES.md
CHANGELOG.md
```

Architecture documentation must distinguish:

- source-derived SATL behavior;
- generic QA-Again product behavior;
- future ideas not implemented.

Do not document a feature as complete until it is tested.

---

# 23. Delivery phases and commits

Work in small, reviewable phases. Adapt file-level details after the repository audit, but preserve these outcomes.

## Phase 00 — Repository audit and constitution

Deliver:

- repository audit;
- architecture decision summary;
- implementation plan;
- baseline test/build status;
- license review.

Commit:

```text
chore: audit repository and establish QA-Again implementation plan
```

Tag after clean verification:

```text
phase-00-repository-audit
```

## Phase 01 — Cloudflare application foundation

Deliver:

- Cloudflare Worker-compatible app;
- Wrangler/OpenNext setup as applicable;
- D1 and R2 bindings;
- local migrations;
- environment validation;
- health endpoint;
- green design tokens and application shell;
- preview/deploy documentation.

Commit:

```text
feat: establish Cloudflare foundation for QA-Again
```

Tag:

```text
phase-01-cloudflare-foundation
```

## Phase 02 — Identity, projects, and roles

Deliver:

- Access identity verification;
- safe local auth mode;
- users/projects/members schema;
- Admin/Tester/Viewer authorization;
- project list/dashboard shell;
- members management;
- PM external-link fields;
- authorization tests.

Commit:

```text
feat: add project-scoped identity and role authorization
```

Tag:

```text
phase-02-project-auth
```

## Phase 03 — Test script import and revisions

Deliver:

- suite management;
- Markdown/Excel/CSV import preview;
- original source saved to R2;
- DRAFT/PUBLISHED revision lifecycle;
- clone revision;
- revision comparison;
- SATL fixture tests;
- no duplicate cases from the historical matrix by default.

Commit:

```text
feat: add test script import and immutable revisions
```

Tag:

```text
phase-03-script-revisions
```

## Phase 04 — Test cycles and execution

Deliver:

- cycle creation from published revision;
- result rows;
- assignments;
- execution UI;
- status policies;
- actual result;
- defect links;
- review and lock;
- result history.

Commit:

```text
feat: add revision-bound test cycles and execution workflow
```

Tag:

```text
phase-04-test-execution
```

## Phase 05 — Evidence studio

Deliver:

- capture one frame from tab/window/screen;
- paste/upload/drag-drop;
- browser resize/compress;
- private R2 upload;
- annotation component integration;
- orange annotations;
- numbered callouts;
- evidence revisions;
- evidence gallery;
- quota accounting;
- no video code.

Commit:

```text
feat: add screenshot evidence capture and annotation studio
```

Tag:

```text
phase-05-evidence-studio
```

## Phase 06 — Reports and Excel export

Deliver:

- dashboard metrics;
- required reports;
- revision and cycle comparison;
- print report;
- customer Excel;
- portable ZIP evidence package;
- export tests with Thai/Unicode content.

Commit:

```text
feat: add QA reports and customer evidence exports
```

Tag:

```text
phase-06-reports-exports
```

## Phase 07 — Hardening and production handover

Deliver:

- threat-model mitigations;
- free-plan capacity guide;
- performance/bundle review;
- accessibility pass;
- full automated suite;
- Cloudflare preview smoke;
- deploy/runbook docs;
- final clean status;
- changelog and handover.

Commit:

```text
chore: harden QA-Again and complete production handover
```

Tag:

```text
phase-07-mvp-handover
```

Do not combine all phases into one giant commit.

After the final phase, create an optional verified Git bundle outside the repository if the environment permits:

```bash
git bundle create ../QA-Again-phase07-mvp.bundle --all
git bundle verify ../QA-Again-phase07-mvp.bundle
```

Do not commit the bundle into the repository.

---

# 24. Definition of Done for the MVP

The MVP is not complete unless all of the following are true:

- QA-Again runs as a standalone app.
- It deploys/previews on Cloudflare Workers.
- D1 stores relational QA data.
- R2 stores private evidence/source files.
- Cloudflare Access identity is validated.
- Project-scoped Admin/Tester/Viewer authorization works.
- Multiple independent projects work.
- PM-Again remains separate and links by URL/reference only.
- Test suites and immutable script revisions work.
- Markdown import works against the supplied SATL regression file.
- Excel and CSV import have preview/mapping.
- A published revision can create multiple independent cycles.
- Old cycles retain the exact original revision.
- Execution supports PASS/NG/BLOCKED/NOT RUN/N/A rules.
- Screenshot capture is single-frame only.
- Paste and upload work.
- Annotation uses an embedded open-source component.
- Original evidence is immutable.
- Evidence revisions and numbered callouts work.
- Private evidence authorization is enforced.
- Green UI and soft-orange NG states are implemented.
- No video feature or video code exists.
- Reports work.
- Excel export opens correctly and contains expected fields.
- Evidence package ZIP works.
- Locked cycles reject mutation.
- Audit history exists.
- Free-plan guardrails and documentation exist.
- Lint, typecheck, tests, build, and Cloudflare preview pass.
- Working tree is clean.

---

# 25. Explicit non-goals for this MVP

Do not implement unless required to satisfy an existing repo dependency:

- video recording;
- video evidence;
- native desktop capture agent;
- browser extension;
- automated Playwright test authoring/execution platform;
- AI test generation;
- OCR;
- public evidence links;
- two-way PM-Again database synchronization;
- billing/subscription system;
- mobile native app;
- complex workflow designer;
- external defect-system integration beyond URL/reference fields;
- server-side heavy PDF generation;
- storing generated reports permanently by default.

Leave clean extension points and document future options, but do not dilute the MVP.

---

# 26. Final response format after implementation

When you finish a phase or the full task, report facts in this structure:

## Repository assessment

- existing stack found;
- major decisions;
- retained/replaced components and reasons.

## Completed work

- grouped by phase;
- routes/features added;
- schema/migrations;
- embedded open-source components and licenses.

## Cloudflare resources

- bindings expected;
- commands already run;
- manual dashboard/account actions still required;
- no secrets printed.

## Verification

Show actual command and result summaries for:

```text
lint
typecheck
unit tests
integration tests
E2E tests
build
Cloudflare preview smoke
```

## Git checkpoint

- commit SHA;
- tag;
- `git status --short --branch`;
- bundle path and verification result if created.

## Remaining limitations

Be explicit. Do not describe incomplete features as complete.

## Next recommended action

Provide exactly the next logical implementation/deployment step.

---

# 27. Working principles

- Inspect before editing.
- Reuse before rewriting.
- Prefer permissive open-source components.
- Verify licenses.
- Keep Cloudflare as the only provider.
- Keep PM-Again and QA-Again separate.
- Protect project boundaries.
- Evidence is a first-class domain object, not a generic attachment.
- Preserve immutable originals and published revisions.
- Optimize for the free plan without making the design impossible to upgrade.
- Do not hide failed commands or skipped tests.
- Do not use placeholder data to claim a feature works.
- Do not commit secrets.
- Do not add video support.
- Make the application useful for SATL while remaining reusable for every future project.

Begin now with the repository audit, baseline verification, and Phase 00 commit. Then continue through the phases in order, stopping only for a truly blocking external Cloudflare action.
