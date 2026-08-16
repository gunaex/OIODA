# AGAIN ECOSYSTEM UX AUDIT — PM AGAIN + QA AGAIN

> Audit date: 2026-08-15
> Scope: READ/INSPECT only — no files were modified during this audit.
> Purpose: define the reusable UX/design foundation for **Document Again**.

---

## 1. Executive Summary

PM Again and QA Again are **near-clone frontends** built on an identical, de-facto shared stack. They were clearly produced from the same template and have since drifted in a small number of deliberate (and a few accidental) ways.

**What is genuinely shared today (evidence-backed):**

| Asset | Verdict | Evidence |
|-------|---------|----------|
| Stack & toolchain | IDENTICAL | Vite 8.1.1, React 19.2.7, Tailwind CSS 4.3.3, react-router-dom 7.18.1, axios 1.18.1, oxlint 1.71.0, vite-plugin-pwa 1.3.0 |
| Auth session layer | VERBATIM identical | `frontend/src/auth/AuthContext.jsx` is byte-for-byte the same in both repos |
| Auth gate wrapper | Identical except one line | `auth/RequireAuth.jsx` — PM additionally mounts `CommandPalette` |
| Login screen | Identical except heading text + accent color | `pages/LoginPage.jsx` |
| User badge | Identical except accent color | `components/UserBadge.jsx` |
| Password confirm modal | Identical except accent color | `components/PasswordConfirmModal.jsx` |
| Status badge primitive | Identical structure | `components/StatusBadge.jsx` — same pill markup, different status→color map |
| App shell pattern | Same shape, diverged in detail | `components/Layout.jsx` — same header/tabs/main skeleton |

**The single most important finding:** every shared component differs from its sibling by exactly **one accent color** (`indigo` in PM vs `emerald` in QA), or by **the status→color map**. There is no explicit design-token system — the "design language" is implicit, expressed as repeated Tailwind class strings.

**The second finding:** the highest-value assets for Document Again (evidence capture, image annotation, comments, revision lifecycle, ecosystem provenance) are **not shared today** — each lives in exactly one app. This means Document Again must either re-implement them or extract them, rather than simply import a shared package.

**Recommendation:** introduce `again-ui` as a **tokens + primitives** package first (very low risk), treat the richer interaction patterns (EvidenceDrawer, AnnotationToolbar, CommentThread, ActivityTimeline) as a **second, opt-in layer**, and do **not** force a big-bang migration of PM/QA.

---

## 2. PM Again Frontend Inventory

- **Repo:** `/Users/kanphong/PM-AGAIN` · remote `gunaex/PM-Again` · branch `main` · HEAD `fa3345d6`
- **Framework/build:** React 19 + Vite 8, Tailwind CSS 4 (CSS-first `@import "tailwindcss"`), react-router-dom 7, axios.
- **Component library:** none (no shadcn/radix/mui/headlessui) — all hand-rolled Tailwind.
- **Icon library:** none (emoji + text glyphs only).
- **Extra deps:** `@uiw/react-md-editor` (markdown), `frappe-gantt` (Gantt).
- **Dark/light mode:** none (light-only, hardcoded classes).
- **PWA:** `vite-plugin-pwa` (service worker, offline shell).

### Structure

```
frontend/src/
├── App.jsx                      # routes: /login, / (ProjectList), /resources, /holidays, /:slug/*
├── api/client.js                # axios instance, withCredentials, all API calls
├── auth/AuthContext.jsx         # session provider (login/logout/me)
├── auth/RequireAuth.jsx         # gate + mounts CommandPalette
├── index.css                    # Tailwind + custom @utility (page-shell, reading-col, table-scroll)
├── hooks/useGlobalHotkey.js
├── components/
│   ├── Layout.jsx               # app shell: header, tab nav, ecosystem status, user badge
│   ├── StatusBadge.jsx          # pill badge, status→color map
│   ├── UserBadge.jsx            # email + role + logout
│   ├── PasswordConfirmModal.jsx # re-auth modal for destructive actions
│   ├── CommentsPanel.jsx        # comment thread (task/document)
│   ├── NoteEditor.jsx           # markdown editor + hashtag autocomplete
│   ├── NoteMarkdown.jsx         # markdown render + wiki-links
│   ├── QuickNoteBar.jsx         # global quick-capture bar
│   ├── LinkedNotesPanel.jsx     # backlinks to notes
│   ├── CommandPalette.jsx       # ⌘K command palette + global search
│   ├── SearchBar.jsx            # header search
│   ├── TagBoard.jsx             # hashtag board
│   ├── EcosystemStatusIndicator.jsx # Account Again / Conductor reachability dots
│   ├── EcosystemSourceBadge.jsx # Conductor DeliveryWorkPackage provenance
│   ├── EffortBudgetGauge.jsx    # budget gauge
│   ├── EffortCalculator.jsx     # function-point effort form
│   ├── GanttAnnotationLayer.jsx # Gantt date annotations
│   ├── ImportExportBar.jsx      # Excel import/export
│   ├── UtilizationHeatmap.jsx   # resource heatmap
│   ├── SetPlanDatesControl.jsx
│   └── noteMarkdownUtils.js, noteNav.js
└── pages/                       # 24 pages: ProjectList, ProjectDashboard, FunctionList,
                                 # TaskList, GanttView, ProgressMatrix, DocumentList, DocumentDetail,
                                 # NoteList, NotesHub, BoardPage, ChangeRequestPage, WhiteboardList,
                                 # WhiteboardEditor, ReportsPage, ProjectSettings, ProjectAllocations,
                                 # ResourcePool, HolidaysAdmin, LoginPage, ForcePasswordChangePage
```

### Accent color

`indigo-600` (primary) / `indigo-700` (hover). Grep count: `indigo-600` ×94, `indigo-700` ×49.

### Custom utilities (PM-only)

Defined in `index.css` via Tailwind v4 `@utility`:

```css
@utility page-shell   { /* fluid width, padding 1rem → 3rem responsive */ }
@utility reading-col  { max-width: 78ch; }
@utility table-scroll { overflow-x: auto; }
```

These three utilities encode PM's page-layout philosophy and do **not** exist in QA.

---

## 3. QA Again Frontend Inventory

- **Repo:** `/Users/kanphong/QA-AGAIN` · remote `gunaex/PM-QA-Again` · branch `main` · HEAD `ea000668`
- **Framework/build:** identical to PM (same versions).
- **Component library:** none.
- **Icon library:** none.
- **Extra deps:** none (leaner than PM).
- **Dark/light mode:** none.
- **PWA:** same `vite-plugin-pwa`.

### Structure

```
frontend/src/
├── App.jsx                      # routes: /login, / (ProjectList), /:slug (Dashboard/Suites/Cycles/Reports)
├── api/client.js
├── auth/AuthContext.jsx         # VERBATIM identical to PM
├── auth/RequireAuth.jsx         # identical minus CommandPalette
├── index.css                    # base Tailwind only — NO custom @utility
├── components/
│   ├── Layout.jsx               # app shell: header, 4 tabs, user badge
│   ├── StatusBadge.jsx          # pill badge, QA status→color map
│   ├── UserBadge.jsx            # identical to PM except accent
│   ├── PasswordConfirmModal.jsx # identical to PM except accent
│   ├── EvidenceGallery.jsx      # evidence capture: screen/clipboard/file
│   ├── AnnotationEditor.jsx     # vanilla-canvas image annotation (8 tools)
│   ├── AutomationProvenance.jsx # hybrid-runner metadata
│   └── EcosystemPanel.jsx       # Conductor QARequest provenance
└── pages/                       # 11 pages: ProjectList, Dashboard, SuiteList, SuiteDetail,
                                 # RevisionDetail, CycleList, CycleExecution, ReportsPage,
                                 # LoginPage, ForcePasswordChangePage
```

### Accent color

`emerald-600` / `emerald-500` (primary) / `emerald-700` (hover). Grep count: `emerald-500` ×37, `emerald-600` ×24, `emerald-700` ×15.

### Notable QA-only assets (highest Document Again value)

| Component | What it does | Document Again relevance |
|-----------|--------------|--------------------------|
| `EvidenceGallery.jsx` | 3 capture paths (screen / clipboard paste / file upload) → authenticated upload, pending-capture lifecycle, object-URL cleanup | **Evidence** — direct |
| `AnnotationEditor.jsx` | vanilla `<canvas>` tools: select/arrow/rectangle/highlight/freehand/text/callout/blur; orange default; undo/redo; JSON shape persistence | **Semantic Annotation** — direct |
| `EcosystemPanel.jsx` | shows Conductor QARequest source, correlationId, qualityGate — renders nothing for manual cycles | **Traceability / provenance** — design pattern |
| `AutomationProvenance.jsx` | hybrid-runner run metadata (browser/version/artifact) | low |

---

## 4. Shared UX Comparison

Legend: `SHARED` / `SIMILAR_BUT_DIVERGED` / `PM_SPECIFIC` / `QA_SPECIFIC` / `MISSING`.

| Pattern | PM source | QA source | Classification | Notes |
|---------|-----------|-----------|----------------|-------|
| App shell (header + tabs + main) | `components/Layout.jsx` | `components/Layout.jsx` | SIMILAR_BUT_DIVERGED | same skeleton; PM fluid `page-shell`, QA `max-w-6xl`; tab sets differ |
| Sidebar | — | — | MISSING | neither uses a sidebar; top tab nav is the nav model |
| Top navigation | `Layout.jsx` `nav` tabs | `Layout.jsx` `nav` tabs | SHARED | pill tabs (`px-4 py-2 rounded-md text-sm`), active = filled accent |
| Page header | `Layout.jsx` header | `Layout.jsx` header | SIMILAR_BUT_DIVERGED | PM shows raw `slug`, QA shows `project.name`; PM adds SearchBar + ecosystem status |
| Spacing | `page-shell` (1→3rem) | `max-w-6xl px-4 sm:px-6` | SIMILAR_BUT_DIVERGED | PM fluid vs QA fixed 1152px cap |
| Typography | `system-ui, Segoe UI, Roboto` | identical | SHARED | both `index.css` |
| Border radius | `rounded-md` (inputs/buttons) `rounded-lg` (cards/modals) `rounded-full` (badges) | identical | SHARED | |
| Surfaces | `bg-gray-50` page, `bg-white` cards, `border-gray-200/300` | identical | SHARED | |
| Shadows | `shadow-2xl` (modal), `shadow-md` (hover) | `shadow-2xl`, `shadow-md` | SHARED | |
| Button hierarchy | primary `bg-{accent}-600`, secondary `border`, danger `bg-red-600` | identical | SHARED (accent only) | |
| Badge / status semantics | `StatusBadge.jsx` (PM map) | `StatusBadge.jsx` (QA map) | SIMILAR_BUT_DIVERGED | pill identical; map app-specific (see §5) |
| Drawer behavior | — (no drawer; modals + inline panels) | — | MISSING | both use modals, not drawers |
| Modal behavior | `PasswordConfirmModal` (centered overlay `bg-black/30`) | identical | SHARED | |
| Tabs | NavLink pill tabs | NavLink pill tabs | SHARED | |
| Tooltips | `title=` attr only (e.g. EcosystemStatusIndicator `Dot`) | `title=` attr only | SHARED | no real tooltip component |
| Tables | `table-scroll` + `table` | inline `overflow-x-auto` + `table` | SIMILAR_BUT_DIVERGED | PM formalized a utility; QA inline |
| Forms | `px-3 py-2 border rounded-md focus:ring-2` | identical | SHARED | |
| Context menus | none found | none found | MISSING | |
| Empty states | inline `text-sm text-gray-400` paragraphs | inline | SHARED | no `EmptyState` component |
| Comments | `CommentsPanel.jsx` | — | PM_SPECIFIC | QA has no comments |
| Notes | `NoteEditor`, `NoteMarkdown`, `QuickNoteBar`, `LinkedNotesPanel`, `TagBoard` | — | PM_SPECIFIC | |
| Annotations | `GanttAnnotationLayer.jsx` (Gantt date-based) | `AnnotationEditor.jsx` (image canvas) | DIVERGED | two unrelated annotation systems |
| Evidence | — | `EvidenceGallery.jsx` | QA_SPECIFIC | PM has none |
| History / timeline | `ActivityLog` (backend only, no dedicated UI component) | revision list in `RevisionDetail.jsx` | PARTIAL | no shared ActivityTimeline component |
| Loading/error/disabled | inline `Loading…` / red banner / `disabled:opacity-50` | identical | SHARED | |
| Dark / light | — | — | MISSING | both light-only |
| Ecosystem provenance | `EcosystemSourceBadge` (blue) + `EcosystemStatusIndicator` | `EcosystemPanel` (indigo) | SIMILAR_BUT_DIVERGED | same idea, different color + shape |
| Command palette / search | `CommandPalette` + `SearchBar` | — | PM_SPECIFIC | |
| Whiteboard entry | `WhiteboardEditor.jsx` (drawio embed) | — | PM_SPECIFIC | |

---

## 5. Design Token Audit

### 5.1 Explicit vs implicit tokens

**There is no explicit token file in either repo.** Tokens are implicit, repeated as raw Tailwind class strings. The only shared "token source" is `index.css`, which differs between the two (PM has extra `@utility`).

### 5.2 Implicit token inventory (measured)

**Typography**
- Font family: `system-ui, 'Segoe UI', Roboto, sans-serif` (both, identical)
- Sizes (used): `text-xs` (badges/meta), `text-sm` (body/controls), `text-base` (default), `text-lg` (page titles), `text-xl` (login title), `text-2xl` (list page title)
- Weights: `font-medium` (labels/buttons), `font-semibold` (headings), `font-bold` (rare)
- No line-height overrides beyond Tailwind defaults

**Spacing**
- Page padding: PM `page-shell` (1rem / 1.5rem / 2rem / 3rem responsive); QA `px-4 sm:px-6`
- Card padding: `p-5` / `p-6` / `p-8`
- Control gap: `gap-2` / `gap-4` / `space-y-3` / `space-y-4`
- Section gap: `py-4` / `py-6` / `mb-4` / `mb-6`

**Radius**
- Cards/modals: `rounded-lg`
- Inputs/buttons/tabs: `rounded-md`
- Badges/dots: `rounded-full`

**Layout**
- Sidebar width: n/a (no sidebar)
- Topbar height: implicit (~`py-4` + content)
- Content max width: PM `page-shell` (fluid) + `reading-col` (78ch); QA `max-w-6xl` (1152px) / `max-w-5xl` (1024px)
- Drawer width: n/a (no drawers)

**Color semantics**

| Semantic | PM | QA | Shared? |
|----------|----|----|---------|
| Primary/accent | `indigo-600/700` | `emerald-600/700` (also `-500`) | NO (deliberate per-app brand) |
| Success/done/pass | `green-100/green-700` | `green-100/green-700` | YES |
| Neutral/draft/todo | `gray-100/gray-600` | `gray-100/gray-600` | YES |
| Warning/review/pending | `yellow-100/yellow-700` | `yellow-100/yellow-700` | YES |
| Danger/fail/blocked | `red-100/red-700` | `red-100/red-700` | YES |
| In-progress/ready/running | `blue-100/blue-700` | `blue-100/blue-700` | YES |
| Ecosystem/source/provenance | `blue-50/200/900` | `indigo-50/200/700` | NO (drift — see below) |

**Interaction states**
- Hover: `hover:bg-{accent}-700` / `hover:bg-gray-100` / `hover:bg-gray-50`
- Focus: `focus:outline-none focus:ring-2 focus:ring-{accent}-500`
- Selected (tabs): `bg-{accent}-600 text-white`
- Disabled: `disabled:opacity-50`
- Loading: inline text `Loading…` (no spinner component)
- Danger: `bg-red-600 hover:bg-red-700`

### 5.3 Where PM and QA intentionally differ vs. drifted

| Item | Intentional? | Evidence |
|------|-------------|----------|
| Accent color (indigo vs emerald) | INTENTIONAL | per-app brand; consistent everywhere including login and favicon theme_color |
| Container (fluid vs fixed 1152px) | DRIFT | PM later added `page-shell` for wide-screen tables; QA never received it |
| Ecosystem provenance color (blue vs indigo) | DRIFT | PM uses `blue`, QA uses `indigo`; same concept, uncoordinated |
| Role naming (`pmo_admin`/`client_viewer` vs `ADMIN`/`TESTER`) | INTENTIONAL but uncoordinated | backend-driven; blocks shared RBAC display |
| Header title (raw slug vs project name) | DRIFT | PM shows slug, QA shows name — minor UX inconsistency |
| Status key casing (Pascal vs SCREAMING) | DRIFT | PM `Draft`/`InProgress`; QA `DRAFT`/`IN_PROGRESS` |

---

## 6. Component Candidate Matrix

For each candidate, classification:
`EXTRACT_NOW` / `EXTRACT_LATER` / `SHARE_PATTERN_ONLY` / `KEEP_APP_SPECIFIC` / `DO_NOT_STANDARDIZE`.

| Component | PM source | QA source | Similarity | Coupling | Extraction risk | Recommendation |
|-----------|-----------|-----------|------------|----------|-----------------|----------------|
| AuthContext | `auth/AuthContext.jsx` | `auth/AuthContext.jsx` | verbatim identical | `api/client.js` | LOW | **EXTRACT_NOW** |
| RequireAuth | `auth/RequireAuth.jsx` | `auth/RequireAuth.jsx` | identical + PM CommandPalette | router, AuthContext | LOW | **EXTRACT_NOW** (accept optional slot) |
| UserBadge | `UserBadge.jsx` | `UserBadge.jsx` | identical except accent | `useAuth` | LOW | **EXTRACT_NOW** (parameterize accent) |
| PasswordConfirmModal | `PasswordConfirmModal.jsx` | `PasswordConfirmModal.jsx` | identical except accent | none | LOW | **EXTRACT_NOW** |
| StatusBadge | `StatusBadge.jsx` | `StatusBadge.jsx` | identical markup, different map | none | LOW-MED | **EXTRACT_NOW** as primitive; normalize semantic map first (§7) |
| Button | (inline in both) | (inline) | identical classes | none | LOW | **EXTRACT_NOW** (currently no Button component — create from repeated classes) |
| Card | (inline) | (inline) | identical classes | none | LOW | **EXTRACT_NOW** |
| Tooltip | `title=` attr | `title=` attr | n/a | none | LOW | **EXTRACT_LATER** (real component needed) |
| Tabs | `Layout.jsx` `tabClass` | `Layout.jsx` `tabClass` | identical pattern | router NavLink | LOW | **SHARE_PATTERN_ONLY** (thin wrapper) |
| Breadcrumb | inline `← Projects` link | inline `← Projects` link | identical | router | LOW | **SHARE_PATTERN_ONLY** |
| EmptyState | inline paragraphs | inline paragraphs | identical | none | LOW | **EXTRACT_LATER** |
| ConfirmDialog | `PasswordConfirmModal` | `PasswordConfirmModal` | identical | none | LOW | **EXTRACT_NOW** (generalize beyond password) |
| Toast | — | — | MISSING | — | — | **DO_NOT_STANDARDIZE** (none exists) |
| PageHeader | `Layout.jsx` header | `Layout.jsx` header | diverged | router, auth | MED | **EXTRACT_LATER** (needs container + title resolution) |
| ProjectSelector | inline in `CommandPalette`/`ProjectList` | — | PM-only | API | MED | **SHARE_PATTERN_ONLY** |
| Sidebar | — | — | MISSING | — | — | **DO_NOT_STANDARDIZE** (neither uses one) |
| ActivityTimeline | (backend `activity_log` only) | revision list | PARTIAL | API | MED | **EXTRACT_LATER** |
| CommentThread | `CommentsPanel.jsx` | — | PM-only | API | MED | **EXTRACT_LATER** (QA/Document need it) |
| NotePanel | `NoteEditor`+`NoteMarkdown`+`LinkedNotesPanel` | — | PM-only | md-editor dep | MED | **KEEP_APP_SPECIFIC** (rich; extract later if Document needs it) |
| EvidenceDrawer | — | `EvidenceGallery.jsx` | QA-only | API + upload | MED-HIGH | **EXTRACT_LATER** (highest Document value) |
| AnnotationToolbar | `GanttAnnotationLayer.jsx` | `AnnotationEditor.jsx` | two unrelated systems | canvas | HIGH | **SHARE_PATTERN_ONLY** (unify grammar, not code, first) |

---

## 7. App-Specific Components

### 7.1 PM-specific (keep specialized)

| Component | Why app-specific |
|-----------|------------------|
| `EffortCalculator.jsx`, `EffortBudgetGauge.jsx` | Function-point effort model (PM estimation domain) |
| `GanttAnnotationLayer.jsx`, `GanttView.jsx` | frappe-gantt dependency; PM schedule domain |
| `ImportExportBar.jsx` | PM Excel import/export with strict header validation |
| `UtilizationHeatmap.jsx`, `SetPlanDatesControl.jsx` | PM resource/scheduling |
| `TagBoard.jsx` | PM hashtag note taxonomy |
| `ProgressMatrix` page | PM Yotei-Jisseki (plan vs actual) |

### 7.2 QA-specific (keep specialized)

| Component | Why app-specific |
|-----------|------------------|
| `SuiteList/SuiteDetail`, `CycleList/CycleExecution` | QA test-suite/cycle lifecycle |
| `AutomationProvenance.jsx` | hybrid-runner metadata |
| `RevisionDetail.jsx` (case editor) | QA test-case authoring |
| `EcosystemPanel.jsx` | QA's QAResult provenance (QA-E8) |

### 7.3 Cross-cutting, currently duplicated but conceptually shared

- **Auth (AuthContext/RequireAuth/UserBadge/PasswordConfirmModal/LoginPage)** — verbatim or near-verbatim duplication; the clearest extraction win.
- **StatusBadge** — duplicated primitive with app-specific maps.
- **Layout shell** — duplicated with drift.

---

## 8. Document Again Reuse Recommendations

Document Again's planned workspace (Requirement Register, UR/DR documents, schema/ERD, data dictionary, process flow, architecture diagram, whiteboard, comments, semantic annotation, evidence, revision history/baseline/compare, traceability, impact analysis, change requests, decisions) maps onto existing patterns as follows:

| Document Again need | Reuse verdict | Source | Why |
|---------------------|---------------|--------|-----|
| Evidence | **REUSE_WITH_REFACTOR** | QA `EvidenceGallery.jsx` | capture grammar (screen/clipboard/file) is canonical; refactor to a shared pattern with a Document-specific backend |
| Semantic Annotation | **REUSE_WITH_REFACTOR** | QA `AnnotationEditor.jsx` | the 8-tool canvas grammar is the single most valuable asset; Document may need to extend it beyond images (schema/ERD surfaces) but the interaction grammar transfers |
| Comments | **REUSE_WITH_REFACTOR** | PM `CommentsPanel.jsx` | currently hard-limited to `task`/`document` entity types; generalize to arbitrary entity |
| Notes / wiki workspace | **REUSE_DESIGN_ONLY** | PM `NoteEditor`+`NotesHub` | rich markdown workspace is a good design reference; keep PM-specific until Document's needs are confirmed |
| Whiteboard entry | **REUSE_DESIGN_ONLY** | PM `WhiteboardEditor.jsx` | drawio embed pattern transfers; the embed itself is app-agnostic |
| Revision history / baseline / compare | **REUSE_DESIGN_ONLY** | QA `RevisionDetail.jsx` | revision lifecycle (DRAFT→PUBLISHED→SUPERSEDED) is a strong design reference for Document's baseline/compare |
| Traceability / provenance | **REUSE_DESIGN_ONLY** | PM `EcosystemSourceBadge` + QA `EcosystemPanel` | the "render nothing unless ecosystem-sourced" pattern is the right model for Document's traceability UI |
| Status / history | **REUSE_DIRECTLY** | `StatusBadge.jsx` (both) | once the semantic map is normalized, Document inherits it directly |
| Context menu / tooltip | **REUSE_WITH_REFACTOR** | (none today) | must be built; use the existing `title=` pattern as the interim baseline |
| Activity timeline | **REUSE_WITH_REFACTOR** | PM backend `activity_log` + QA revision list | no shared component exists; Document should be the first consumer of a shared ActivityTimeline |
| Change requests / impact analysis / decisions | **REUSE_DESIGN_ONLY** | PM `ChangeRequestPage.jsx` | lifecycle (Draft→UnderAnalysis→PendingApproval→Approved) transfers; Document's change model is its own |

**Summary:** Document Again should **reuse directly** the status/token language and the auth shell, **reuse with refactor** the evidence + annotation + comment patterns (extracting them into shared patterns), and **design-only** the revision, whiteboard, and change-request flows.

---

## 9. Proposed again-ui Boundary

The proposed three-layer structure **fits the actual code well**, with one adjustment.

```
again-ui/
├── tokens/
│   ├── accent.ts            # indigo vs emerald vs (Document's accent) — per-app brand
│   ├── semantic-status.ts   # normalized status → color mapping
│   ├── radius.ts            # md / lg / full
│   ├── spacing.ts           # page/card/control gaps
│   ├── typography.ts        # system-ui stack, size scale
│   └── interaction.ts       # hover/focus/disabled/danger
│
├── primitives/
│   ├── Button
│   ├── Badge
│   ├── StatusBadge          # wraps Badge + semantic-status tokens
│   ├── Card
│   ├── Modal
│   ├── ConfirmDialog        # generalize PasswordConfirmModal
│   ├── Tabs                 # thin NavLink wrapper
│   ├── Tooltip
│   └── EmptyState
│
└── patterns/               # OPT-IN, not forced
    ├── AuthProvider        # extract verbatim AuthContext/RequireAuth
    ├── UserBadge
    ├── CommentThread
    ├── EvidenceDrawer
    ├── AnnotationToolbar
    └── ActivityTimeline
```

**Adjustment vs the original proposal:** `AuthProvider`/`UserBadge` are the highest-value, lowest-risk extractions and should live in `patterns/` (or a thin `auth/` slice) **from day one** — they are already verbatim duplicates and will otherwise drift independently. The original proposal omitted auth; including it is the single cheapest consistency win.

**Boundary rule established by the evidence:**
1. **Design tokens** → normalize the implicit color/radius/spacing/status language.
2. **Shared primitives** → Button/Badge/Card/Modal/etc. (de-facto shared already).
3. **App-specific workspace** → effort, gantt, test suites, evidence capture UI itself (the *data model* is shared; the *workspace layout* is app-specific).

The evidence shows the apps **already behave** as if this boundary exists — it just isn't codified in a package.

---

## 10. Risks / Technical Debt

1. **No token system** — 94× `indigo-600` in PM, 37× `emerald-500` in QA. Extraction requires a class-name search-and-replace with token indirection; do it via a codemod or a CSS-variable layer, not by hand.
2. **Status semantic drift** — PM keys are Pascal (`Draft`, `InProgress`), QA keys are SCREAMING (`DRAFT`, `IN_PROGRESS`). A shared StatusBadge must normalize keys or accept both.
3. **Ecosystem color drift** — PM uses `blue` for provenance, QA uses `indigo`. `indigo` is PM's brand color, so QA's use of indigo-for-ecosystem is semantically overloaded and must be resolved before standardizing.
4. **Container drift** — PM `page-shell` (fluid) vs QA `max-w-6xl` (fixed). Document Again must choose; recommend adopting PM's `page-shell` (fluid, wide-screen friendly) as the ecosystem standard.
5. **Role model divergence** — PM `pmo_admin/dev/qa/client_viewer` vs QA `ADMIN/TESTER`. Shared UserBadge/auth can't standardize authorization display until roles converge (Account Again will eventually own this).
6. **No dark mode** — both light-only; a future token layer should not paint itself into a light-only corner.
7. **No component tests** — extraction must introduce tests or regression risk is high.
8. **No tooltip/context-menu/toast components** — Document Again needs them; they must be built, not extracted.
9. **Duplication is already drifting** — PM's extra `page-shell`/`reading-col`/`table-scroll` utilities and `CommandPalette` have no QA counterpart; every day of delay widens the gap.

---

## 11. Recommended Extraction Sequence

The proposed sequence is **validated**, with one refinement (auth first):

1. **Document existing ecosystem tokens** — audit the implicit color/radius/spacing/status language into `tokens/` (zero code change). *(validated)*
2. **Normalize semantic status definitions** — agree one status→color map across PM/QA; resolve the `blue` vs `indigo` ecosystem color and the key-casing divergence. *(validated — this is a prerequisite, not a nicety)*
3. **Extract very low-risk primitives** — Button, Badge, Card, Modal, ConfirmDialog, StatusBadge. *(validated)*
4. **Extract verbatim auth** — AuthContext/RequireAuth/UserBadge (highest duplication, lowest risk). *(refinement)*
5. **Extract interaction patterns proven shared** — CommentThread, EvidenceDrawer, AnnotationToolbar — only after Document Again confirms its needs, so the API isn't over-fit to PM or QA. *(validated, moved later)*
6. **Let Document Again consume them** — build Document's specialized workspace (ERD canvas, diff/baseline viewer, traceability matrix) on top of the shared tokens/primitives. *(validated)*
7. **Only later migrate/refactor PM Again and QA Again** where useful — low priority; do not destabilize working apps. *(validated)*

**Avoid a big-bang design-system refactor.** Ship tokens + primitives + auth as an additive package; migrate PM/QA incrementally and only where it removes real duplication.

---

## 12. Final Decision Matrix

| Question | Answer |
|----------|--------|
| What already constitutes the AGAIN design language? | Tailwind v4 class conventions: `system-ui` type, `rounded-md/lg/full`, `bg-gray-50` + `bg-white` + `border-gray-200`, pill badges, centered modal overlay, pill tab nav, and a consistent green/gray/yellow/red/blue status family. Accent color is the one deliberate per-app variable. |
| What should become shared tokens? | Accent (parameterized), semantic-status colors, radius, spacing, typography, interaction states (hover/focus/disabled/danger). |
| What should become shared components? | Button, Badge/StatusBadge, Card, Modal, ConfirmDialog, Tabs, Tooltip, EmptyState, plus auth (AuthContext/RequireAuth/UserBadge). |
| What should remain PM-specific? | Effort calculator, Gantt, Excel import/export, utilization heatmap, progress matrix, tag board. |
| What should remain QA-specific? | Test suites/cycles, test-case editor, hybrid-runner provenance. |
| Which PM/QA patterns should Document Again inherit? | Status language (directly), evidence capture + image annotation + comments (via refactor), revision/whiteboard/change-request flows (design-only). |
| What should Document Again build as specialized workspace UX? | ERD/schema canvas, data dictionary, document diff/baseline viewer, traceability matrix, decision log, semantic annotation surfaces beyond images. |
| Can we safely introduce again-ui now without destabilizing PM/QA? | YES — as an additive tokens+primitives+auth package consumed by Document Again first; migrate PM/QA incrementally. |
| Lowest-risk extraction sequence? | tokens → normalize status → primitives → auth → patterns (as Document needs them) → migrate PM/QA later. |

---

## Appendix A — Exact source paths cited

- PM: `/Users/kanphong/PM-AGAIN/frontend/src/{App.jsx,index.css,auth/AuthContext.jsx,auth/RequireAuth.jsx,components/{Layout,StatusBadge,UserBadge,PasswordConfirmModal,CommentsPanel,NoteEditor,NoteMarkdown,QuickNoteBar,LinkedNotesPanel,CommandPalette,SearchBar,TagBoard,EcosystemStatusIndicator,EcosystemSourceBadge,GanttAnnotationLayer,EffortCalculator,EffortBudgetGauge,ImportExportBar,UtilizationHeatmap,SetPlanDatesControl}.jsx,pages/{LoginPage,ProjectList,DocumentDetail,WhiteboardEditor,ProgressMatrix,ChangeRequestPage,BoardPage,NotesHub}.jsx}`
- QA: `/Users/kanphong/QA-AGAIN/frontend/src/{App.jsx,index.css,auth/AuthContext.jsx,auth/RequireAuth.jsx,components/{Layout,StatusBadge,UserBadge,PasswordConfirmModal,EvidenceGallery,AnnotationEditor,AutomationProvenance,EcosystemPanel}.jsx,pages/{LoginPage,ProjectList,RevisionDetail,SuiteDetail,CycleExecution}.jsx}`

## Appendix B — Method note

This audit was performed by reading actual source files and diffing paired components across the two repos. Classification (`SHARED` vs `SIMILAR_BUT_DIVERGED` etc.) is based on implementation diffs, not component names. No files were modified, no dependencies installed, no commits made, and both working trees remain untouched.
