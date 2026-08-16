// Centralized glossary — the single source for help/term definitions.
// Components must not hardcode conflicting definitions.

export const GLOSSARY = [
  {
    term: "UR",
    simple: "User Requirement document.",
    detailed: "The user-facing requirement document. Its sections carry stable semantic ids and reference canonical Requirements. It is a generated view over structured knowledge, not the source of truth.",
  },
  {
    term: "DR",
    simple: "Design/Technical Requirement document.",
    detailed: "The technical design document. Confirming a DR revision atomically freezes all bound technical designs (DB, flows, APIs, architecture) into the revision snapshot.",
  },
  {
    term: "Baseline",
    simple: "A frozen set of artifact→revision bindings.",
    detailed: "A named, immutable freeze of exact artifact→revision pairs. It never re-resolves to the latest revision, so a historical export always reproduces the design as it was.",
  },
  {
    term: "Traceability",
    simple: "Links between semantic objects.",
    detailed: "Directed, typed edges (DERIVED_FROM, IMPLEMENTS, …) between stable semantic ids. Only explicitly created links exist — nothing is inferred.",
  },
  {
    term: "Change Request",
    simple: "A controlled change that spawns new revisions.",
    detailed: "A first-class object linking affected semantic objects and their impact. Implementing it clones affected artifacts into new revisions; it never mutates a confirmed baseline.",
  },
  {
    term: "Primary Key",
    simple: "The field(s) that uniquely identify a row.",
    detailed: "A database field marked primary_key. Represented in the ERD with a 🔑 marker and used as the target anchor for relations.",
  },
  {
    term: "Foreign Key",
    simple: "A field that references another table's key.",
    detailed: "A database field marked foreign_key, storing a reference to another field. Represented in the ERD with a 🔗 marker; relations anchor to it.",
  },
  {
    term: "Semantic Object",
    simple: "A stable identity (REQ-0042, tbl_orders, flow_x…).",
    detailed: "The identity layer used by traces, annotations, baselines and exports. Display names may change; semantic ids never do.",
  },
  {
    term: "Revision",
    simple: "One immutable version of an artifact.",
    detailed: "The unit of confirmation. DRAFT is editable; CONFIRMED is immutable. Editing a confirmed artifact clones a new revision and preserves ancestry.",
  },
  {
    term: "Confirmation",
    simple: "Freezing a revision as immutable.",
    detailed: "Records confirmed-by, confirmed-at, comment and evidence. Confirming a DR also snapshots technical designs atomically — a failure rolls back the whole confirmation.",
  },
];
