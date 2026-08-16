# Document Again — Product / Architecture Handover (P0 Reference)

This file preserves the original P0 product and architecture handover
used to start implementation. It is a reference, not a living spec.
Living documents live alongside it in `docs/`.

---

Document Again is **not** a normal document editor and **not** merely
an AI document generator.

Its role is:

```text
Living Requirement
+
Technical Design Workspace
+
Revision / Baseline Authority
+
User Confirmation Authority
+
Traceability / Change / Impact Memory
```

The core principle is:

```text
Files are outputs.

Structured versioned design knowledge
is the source of truth.
```

## Ecosystem authority boundary

```text
Conductor Again
= Requirement Intake / Delivery Orchestration

Document Again
= Requirement + Design + Revision + Confirmation Authority

PM Again
= Execution / Project Visibility Authority

QA Again
= QA Result / Verification Authority

Account Again
= Identity / Tenant / Entitlement / Trust Authority
```

Document Again does not duplicate PM or QA execution responsibilities.

## P0 entities

Project, Artifact, ArtifactRevision, Baseline, SemanticObject,
Requirement, DesignObject, DatabaseSchema, DatabaseTable,
DatabaseField, DatabaseRelation, ProcessFlow, ProcessStep,
APIEndpoint, Annotation, CommentThread, Decision, Assumption,
Clarification, ChangeRequest, TraceLink, Review, Confirmation,
Release.

## Artifact types

REQUIREMENT_REGISTER, UR, DR, DATABASE_SCHEMA, ER_DIAGRAM,
DATA_DICTIONARY, PROCESS_FLOW, ARCHITECTURE, API_DESIGN,
WHITEBOARD, NOTE, CHANGE_REQUEST, DECISION.

## Revision lifecycle

```text
DRAFT → editable
IN_REVIEW → review/comment allowed
CONFIRMED → immutable
SUPERSEDED → historical immutable
ARCHIVED → historical
```

Confirmed revisions must never be directly edited. Editing a confirmed
artifact uses **Clone as New Revision**. Ancestry is preserved.

A baseline freezes the exact revision relationships that existed when
confirmed. Later child revisions must not alter an old baseline.

## Semantic identity

Traceability and annotation bind to stable semantic object IDs
(`REQ-0042`, `tbl_approval_history`, `api_order_approve`), not pixel
coordinates or document text positions.

## AI boundary

AI is never a source of truth. AI must never confirm requirements,
approve designs, invent traces as fact, overwrite confirmed baselines,
or silently modify schema. P0 has no AI integration.

## P0 non-goals

Google Docs-grade realtime collaboration, full BPMN, enterprise DMS,
complex ACL, digital signatures, database migration execution,
autonomous AI approval, large workflow engine, service mesh, full ERD
editor, full architecture designer, full whiteboard, autonomous AI
trace generation.
