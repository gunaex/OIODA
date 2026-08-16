# OIDA POST-R1 BACKLOG

Useful but not necessary for the unified owner workflow. None of these block
dogfood; each is tracked here instead of being built now.

## Authentication / identity
- Full Account-Again human SSO (single JWT issued to a human, consumed by all services).
- Cross-origin production reverse proxy + cookie `SameSite=None; Secure`.
- Password sync between PM/QA/Conductor user stores (today each has its own email account).

## Conductor visibility
- Sync-failure panel with correlation-id drill-down (today only success is shown).
- Read-only Conductor handoff list inside the shell (beyond Document's ecosystem-trace).

## Document experience
- Full Tiptap editing inside the shell (today the shell renders read-only).
- Semantic diff viewer for revisions/change-sets.
- In-shell ERD / flow editing.

## Planning
- Gantt editing inside the shell (drag dates) — PM has it standalone.
- Dependency graph rendering (PM stores dependencies as comma-separated ids).

## QA
- Test case editor inside the shell (QA has it standalone).
- Evidence upload/annotation inside the shell.
- Hybrid-run checkpoint UI.

## Administration
- Role/entitlement editing (today read-only).
- Credential-reference rotation UI.

## Explicitly out of scope (per Excel policy)
- DOCX/PDF parity with XLSX.
