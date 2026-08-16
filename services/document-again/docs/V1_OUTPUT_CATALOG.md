# Document Again v1.0 — Output Catalog

Supported export formats (all derived from frozen revision/baseline snapshots —
never live state):

| Output | Formats | Notes |
|---|---|---|
| Revision document | JSON / PDF / DOCX / CSV / XLSX | UR, DR |
| ERD | SVG / PNG | from technical-design snapshot |
| Process flow | SVG / PNG | from technical-design snapshot |
| Architecture | SVG / PNG | all diagrams or per-diagram |
| Data dictionary | CSV / XLSX | from snapshot |
| Traceability matrix | XLSX | current trace links (labelled) |
| OpenAPI | JSON | from revision snapshot API endpoints |
| Design package | ZIP (v2, v4) | directory-structured, baseline-scoped |
| Requirement register | XLSX | via script (P6) |
| Project memory registers | XLSX | clarifications/assumptions/decisions via script |

Not applicable by default: Database/ERD (infrastructure-only projects) and API
(no customer API) — Document Again correctly reports NOT_APPLICABLE rather than
inventing deliverables.
