# TRUE CLOUD MIGRATION — Requirement Coverage Report

Source: customer SOW / scope requirement (Track 1 + Track 2). Source text preserved verbatim in the requirement register (`source_type=SOW`).

## Track 1 — Landing Zone and Foundational Services Enhancement

| Original SOW item | Derived atomic requirement | Domain | Deliverable | Clarification | Assumption |
|---|---|---|---|---|---|
| 1. Legacy Zone HLD/LLD | REQ-T1-001 | ARCHITECTURE | Design document | OPEN | — |
| 2. As-built (Landing Zone / Legacy Zone / Thailand) | REQ-T1-002 | ARCHITECTURE | As-built | OPEN | Thailand Region target |
| 3. Core services design/as-built (AD/DNS/firewall/Jump Host/CyberArk) | REQ-T1-003 | IDENTITY | Design + as-built | OPEN | — |
| 4. Jump Host + CyberArk migrated | REQ-T1-004, REQ-T1-005 | MIGRATION | Migrated servers | — | — |
| 5. Connectivity review (on-prem/DX/Azure/GCP) | REQ-T1-006 | CONNECTIVITY | Assessment | OPEN | — |

## Track 2 — Mass Migration Factory

| Original SOW item | Derived atomic requirement | Domain | Deliverable | Clarification | Assumption |
|---|---|---|---|---|---|
| 1. Migration Factory design | REQ-T2-001 | MIGRATION | Design document | OPEN | — |
| 2. Migration network foundation as-built | REQ-T2-002 | NETWORK | As-built | — | — |
| 3. MGN agent enablement | REQ-T2-003 | MIGRATION | Config summary | — | private-path replication |
| 4. Pilot test / verification | REQ-T2-004 | TEST / VERIFICATION | Test report | OPEN (acceptance criteria) | private-path |
| 5. Runbooks / handover | REQ-T2-005 | OPERATIONS | Runbook | OPEN (handover ownership) | — |

## Trace coverage

- TOTAL_REQUIREMENTS: 11 (6 Track 1 + 5 Track 2)
- TRACED_REQUIREMENTS: 11
- UNTRACED_REQUIREMENTS: none
- TRACE_COVERAGE: **100%**

## Open clarifications (7)

1. Target AWS account / OU structure
2. Approved CIDR ranges
3. Direct Connect bandwidth / redundancy model
4. Pilot acceptance criteria
5. Firewall vendor / model
6. Migration workload count / wave plan
7. RTO/RPO per workload class

## Assumptions (2)

1. Migration traffic remains on private network paths (private-path replication) — supported by SOW wording, still labelled as an assumption.
2. Thailand Region is the primary AWS target region.

## Design decisions (1)

1. Deliverables are design/as-built documentation, not a deployment implementation.

## Explicitly NOT_APPLICABLE

- **Database design** — no application database deliverable stated in the SOW.
- **API design** — no customer API requirement stated in the SOW.

## UR / DR / Architecture / Flow coverage

- UR v1.0: 17 sections covering purpose, scope, both tracks, functional/connectivity/security/migration/verification, assumptions, clarifications, out-of-scope, acceptance, traceability.
- DR v1.0: 31 sections (design objectives → landing zone → legacy zone → network/security/logging/governance → AD/DNS/firewall/Jump Host/CyberArk → connectivity/Direct Connect/Azure/GCP → migration factory/staging/endpoints/security groups → MGN/replication/pilot/waves → rollback/handover/traceability).
- Architecture: 2 diagrams (Track 1 Landing Zone, Track 2 Migration Factory), 16 + 8 nodes.
- Flows: 2 (Migration Factory/Workload Migration Flow, Migration Wave Operational Flow).
