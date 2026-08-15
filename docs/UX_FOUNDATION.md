# Document Again — UX Foundation

Document Again reuses the AGAIN ecosystem interaction grammar
(app shell, sidebar, top header, typography, spacing, buttons, cards,
badges, status semantics, comments, annotation, evidence, history)
while adding a specialized high-density center workspace.

Target ratio: **~80% ecosystem consistency, ~20% Document Again
specialized workspace.**

## Stack

React 19 · Vite 8 · Tailwind 4 · React Router 7. Ports: frontend
`:5175`, backend `:8002` (chosen not to collide with PM/QA).

## Design tokens

Tokens live in `frontend/src/index.css` under Tailwind `@theme`.
They are intentionally split:

```text
Brand / app identity        vs        semantic status colors
--color-brand-*                       --color-status-*
```

- **Brand** — deep indigo (`brand-600: #4f46e5`), used for the app
  badge, active nav, focus, primary buttons. It never carries meaning.
- **Semantic status** — the meaning palette shared in intent with
  PM/QA:

```text
DRAFT        slate
IN_REVIEW    amber
CONFIRMED    emerald
SUPERSEDED   slate (dim)
ARCHIVED     slate (darker)
OPEN         amber
RESOLVED     emerald
BLOCKED      red
PASS         emerald
FAIL         red
WARNING      amber
```

Status meaning never borrows the brand accent.

### Neutral surfaces (high-density)

`surface-0..3` and `line` provide the dark workspace canvas and
borders used by every card, table, and panel.

## App shell

```text
┌──────────────────────────────────────────────────────┐
│ Header: DA badge · product · project selector · focus │
├──────────────┬───────────────────────────┬───────────┤
│ Left Nav     │      Main Workspace       │ Context   │
│ PROJECT      │  Requirements / UR / DR / │ Comments  │
│  Requirements│  Database / Flows / APIs  │ Trace     │
│  UR          │  …                        │ Impact    │
│ DESIGN       │                           │           │
│  DR · DB ·   │                           │           │
│  Flows · APIs│                           │           │
│  Architecture│                           │           │
│ GOVERNANCE   │                           │           │
│  Decisions   │                           │           │
│  Reviews     │                           │           │
│  Comments    │                           │           │
│  CRs         │                           │           │
│  Baselines   │                           │           │
└──────────────┴───────────────────────────┴───────────┘
```

## Navigation map

- **PROJECT** — Requirement Register, UR
- **DESIGN** — DR, Database (Schemas / Tables / Fields / Data
  Dictionary), Process Flows, APIs, Architecture
- **GOVERNANCE** — Decisions, Reviews, Comments, Change Requests,
  Baselines

## Implemented surfaces (P0)

- `Projects` — first-project creation
- `Requirements` — canonical requirement register (create + list)
- `Artifacts` (UR/DR) — revision list with full lifecycle: edit draft,
  submit for review, confirm, clone as new revision; 409 errors are
  surfaced verbatim so invariants are visible
- `Database` — Schemas/Tables/Fields model page + Data Dictionary view
- `Comments` — global annotation list
- `ChangeRequests` — create CR, implement (spawn revisions)
- `Baselines` — freeze the confirmed revision of every artifact
- `ContextPanel` (right) — Comments / Trace / Impact, bound to the
  focused semantic object

## Placeholders (P1 engines)

Process Flows, APIs, Architecture, Decisions, Reviews — each renders
an explicit placeholder explaining that the structured model and
semantic IDs already reserve that ground, and the interactive engine
ships post-P0.

## Shared primitives

`frontend/src/components/ui.jsx` — `StatusBadge`, `Button`, `Card`,
`Empty`, `ErrorNote`, `Field`, `inputClass`. Status badge colors come
from the semantic palette, not the brand accent.
