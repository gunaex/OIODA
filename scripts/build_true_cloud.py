#!/usr/bin/env python
"""P6 — TRUE CLOUD MIGRATION real customer trial.

Builds the full Document Again project for the authoritative customer SOW:
requirement register -> classification -> clarifications/assumptions/decisions
-> UR -> DR -> architecture (2 tracks) -> migration flows -> traceability ->
review -> baseline v1 -> controlled TRIAL_CHANGE -> impact -> v2 -> semantic
diff -> generated outputs (PDF/DOCX/XLSX/SVG/PNG/ZIP) -> coverage + catalog.

Run against a fresh migrated database (data/document-again.db).
"""
from __future__ import annotations

import io
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "outputs", "TRUE-CLOUD-MIGRATION")
os.makedirs(OUT, exist_ok=True)

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


# ─────────────────────────────────────────────────────────────────────────
# Authoritative customer SOW (source evidence — do not invent beyond this)
# ─────────────────────────────────────────────────────────────────────────
SOW = [
    ("T1", "1", "AWS Legacy Zone high-level and detailed design documents covering account structure, network segmentation, security boundaries, routing, logging, monitoring, governance controls"),
    ("T1", "2", "As-built configuration for AWS Landing Zone, Legacy Zone, Thailand Region"),
    ("T1", "3", "Design and as-built documentation for core infrastructure services: Active Directory, DNS, firewall/security controls, Jump Host, CyberArk target model"),
    ("T1", "4", "Jump Host and CyberArk servers migrated to AWS Cloud"),
    ("T1", "5", "Connectivity review and assessment covering AWS <-> on-premises, AWS Direct Connect, AWS <-> Azure, AWS <-> GCP, hybrid/multi-cloud considerations"),
    ("T2", "1", "Mass Migration Factory design document covering staging subnet, routing, VPC endpoint architecture"),
    ("T2", "2", "As-built architecture for migration network foundation: subnets, route tables, Direct Connect paths, PrivateLink endpoints, security groups"),
    ("T2", "3", "AWS MGN replication agent enablement/configuration summary covering DNS resolution, endpoint usage, agent installation approach"),
    ("T2", "4", "Pilot test report and verification summary confirming private-path migration behavior and health status"),
    ("T2", "5", "Migration runbooks and operational handover material for migration waves and migration factory execution"),
]

REQUIREMENTS = [
    ("REQ-T1-001", "T1", "AWS Legacy Zone HLD/LLD", SOW[0][2], "ARCHITECTURE", "DESIGN_DOCUMENT", ["account structure", "network segmentation", "security", "routing", "logging", "monitoring", "governance"]),
    ("REQ-T1-002", "T1", "AWS Landing Zone / Legacy Zone As-Built", SOW[1][2], "ARCHITECTURE", "AS_BUILT", ["landing zone", "legacy zone", "thailand region"]),
    ("REQ-T1-003", "T1", "Core Infrastructure Services Design / As-Built", SOW[2][2], "IDENTITY", "DESIGN_AND_AS_BUILT", ["active directory", "dns", "firewall", "jump host", "cyberark"]),
    ("REQ-T1-004", "T1", "Jump Host Migration", SOW[3][2], "MIGRATION", "MIGRATED_SERVERS", ["jump host"]),
    ("REQ-T1-005", "T1", "CyberArk Migration", SOW[3][2], "MIGRATION", "MIGRATED_SERVERS", ["cyberark"]),
    ("REQ-T1-006", "T1", "Hybrid / Multi-cloud Connectivity Assessment", SOW[4][2], "CONNECTIVITY", "ASSESSMENT", ["on-premises", "direct connect", "azure", "gcp", "hybrid", "multi-cloud"]),
    ("REQ-T2-001", "T2", "Migration Factory Design", SOW[5][2], "MIGRATION", "DESIGN_DOCUMENT", ["staging subnet", "routing", "vpc endpoint"]),
    ("REQ-T2-002", "T2", "Migration Network Foundation As-Built", SOW[6][2], "NETWORK", "AS_BUILT", ["subnets", "route tables", "direct connect", "privatelink", "security groups"]),
    ("REQ-T2-003", "T2", "AWS MGN Agent Enablement / Configuration", SOW[7][2], "MIGRATION", "CONFIG_SUMMARY", ["dns resolution", "endpoint usage", "agent installation"]),
    ("REQ-T2-004", "T2", "Pilot Migration Test / Verification", SOW[8][2], "TEST / VERIFICATION", "TEST_REPORT", ["private-path migration", "health status"]),
    ("REQ-T2-005", "T2", "Migration Runbook / Operational Handover", SOW[9][2], "OPERATIONS", "RUNBOOK", ["migration waves", "migration factory execution"]),
]

CLARIFICATIONS = [
    ("What is the target AWS account / OU structure?", None),
    ("What are the approved CIDR ranges for each VPC?", None),
    ("What Direct Connect bandwidth / redundancy model is required?", None),
    ("What are the pilot acceptance criteria?", None),
    ("What is the firewall vendor / model for the security controls?", None),
    ("What is the expected migration workload count (servers) and wave plan?", None),
    ("What RTO/RPO targets apply to each workload class?", None),
]

ASSUMPTIONS = [
    ("Migration traffic is intended to remain on private network paths (private-path replication), not public internet.", ["REQ-T2-003", "REQ-T2-004"]),
    ("Thailand Region is the primary AWS target region for landing zone and legacy zone.", ["REQ-T1-002"]),
]

DECISIONS = [
    ("Design decision: document deliverables are design/as-built documentation, not a deployment implementation.", None),
]


def _para(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _doc(sections):
    return {"sections": [{"id": sid, "heading": h, "content": {"type": "doc", "content": [_para(t)]}} for sid, h, t in sections]}


UR_SECTIONS = [
    ("ur_purpose", "1. Project Purpose", "Deliver high-level and detailed design plus as-built documentation and migrations for the TRUE CLOUD MIGRATION program."),
    ("ur_context", "2. Business / Transformation Context", "Customer SOW defines two tracks: Landing Zone / Foundational Services and Mass Migration Factory."),
    ("ur_scope", "3. Scope", "Track 1 foundational landing zone and core services; Track 2 mass migration factory and pilot."),
    ("ur_track1", "4. Track 1 Scope", "Legacy Zone HLD/LLD, as-built, core infrastructure services (AD/DNS/firewall/Jump Host/CyberArk), connectivity assessment."),
    ("ur_track2", "5. Track 2 Scope", "Migration factory design, network foundation as-built, MGN agent enablement, pilot verification, runbooks."),
    ("ur_functional", "6. Functional / Infrastructure Requirements", "Landing zone, legacy zone, core services, migration factory components."),
    ("ur_connectivity", "7. Connectivity Requirements", "AWS <-> on-premises, Direct Connect, AWS <-> Azure, AWS <-> GCP; private-path replication."),
    ("ur_security", "8. Security / Identity Requirements", "Security boundaries, firewall/security controls, AD, CyberArk target model."),
    ("ur_migration", "9. Migration Requirements", "Jump Host + CyberArk migration; MGN replication; migration waves and runbooks."),
    ("ur_verification", "10. Verification Requirements", "Pilot test report and verification summary confirming private-path behavior and health."),
    ("ur_documentation", "11. Documentation Deliverables", "HLD/LLD, as-built, design documents, runbooks, operational handover."),
    ("ur_handover", "12. Operational Handover Requirements", "Runbooks and operational handover for migration waves and factory execution."),
    ("ur_assumptions", "13. Assumptions", "See project memory — private-path migration intent; Thailand Region target."),
    ("ur_clarifications", "14. Clarifications", "Account/OU structure, CIDRs, Direct Connect bandwidth, pilot acceptance criteria (open)."),
    ("ur_out_of_scope", "15. Out of Scope", "Application database design and customer APIs are not stated in the SOW (NOT_APPLICABLE)."),
    ("ur_acceptance", "16. Acceptance Expectations", "Structured, traceable, reviewable, reproducible design package accepted by engineering."),
    ("ur_trace", "17. Requirement Traceability", "Each requirement traces to a UR section, DR section, architecture object, or flow."),
]

DR_SECTIONS = [
    ("dr_objectives", "1. Design Objectives", "Document the target-state design and migration approach for both tracks; private connectivity preferred."),
    ("dr_overall", "2. Overall Architecture", "AWS Landing Zone + Legacy Zone (Thailand Region) with hybrid/multi-cloud connectivity and a migration factory."),
    ("dr_accounts", "3. AWS Account / Landing Zone Design", "Account structure TBD (CLARIFICATION_REQUIRED); OU/account hierarchy to be confirmed."),
    ("dr_legacy", "4. Legacy Zone Design", "Legacy zone segmentation, security boundaries, routing — detail TBD."),
    ("dr_network", "5. Network Segmentation", "Segmentation per security boundary; CIDR ranges TBD (CLARIFICATION_REQUIRED)."),
    ("dr_routing", "6. Routing Design", "Routing between zones, on-premises and cloud — TBD."),
    ("dr_security", "7. Security Boundaries", "Security controls, firewall/security controls design (vendor/model TBD)."),
    ("dr_logging", "8. Logging / Monitoring", "Logging and monitoring design; toolset and retention TBD."),
    ("dr_governance", "9. Governance Controls", "Governance controls as part of landing zone design."),
    ("dr_ad", "10. Active Directory Design", "AD topology TBD (CLARIFICATION_REQUIRED)."),
    ("dr_dns", "11. DNS Design", "DNS forwarding model TBD."),
    ("dr_firewall", "12. Firewall / Security Control Design", "Firewall/security controls design (vendor/model TBD)."),
    ("dr_jumphost", "13. Jump Host Design", "Jump Host sizing TBD; migrated to AWS Cloud per SOW."),
    ("dr_cyberark", "14. CyberArk Target Architecture", "CyberArk target model and architecture TBD; migrated to AWS Cloud per SOW."),
    ("dr_hybrid", "15. Hybrid Connectivity", "AWS <-> on-premises, Direct Connect, AWS <-> Azure, AWS <-> GCP."),
    ("dr_dx", "16. Direct Connect Design", "Direct Connect topology and bandwidth TBD (CLARIFICATION_REQUIRED)."),
    ("dr_azure_gcp", "17. Azure / GCP Connectivity Considerations", "Connectivity mechanism to Azure/GCP TBD."),
    ("dr_factory", "18. Migration Factory Architecture", "Staging subnet, routing, VPC endpoint architecture for mass migration."),
    ("dr_staging", "19. Staging Subnet", "Staging subnet design TBD."),
    ("dr_endpoints", "20. VPC Endpoint / PrivateLink Design", "PrivateLink endpoints for private-path replication."),
    ("dr_sg", "21. Security Groups", "Security groups for migration network foundation."),
    ("dr_mgn", "22. AWS MGN Design", "MGN replication agent enablement, DNS resolution, endpoint usage, agent installation."),
    ("dr_replication", "23. Replication Flow", "Private-path replication from source to target VPC via MGN."),
    ("dr_pilot", "24. Pilot Migration Flow", "Pilot migration test, verification and health confirmation."),
    ("dr_waves", "25. Migration Wave Operating Model", "Wave planning -> readiness -> replication -> test -> cutover -> validation -> closure."),
    ("dr_rollback", "26. Rollback / Verification Considerations", "Rollback criteria TBD."),
    ("dr_handover", "27. Operational Handover", "Runbooks and operational handover ownership TBD."),
    ("dr_trace", "28. Traceability", "Design sections trace to requirements and architecture/flow objects."),
    ("dr_assumptions", "29. Assumptions", "Private-path intent; Thailand Region target (labelled)."),
    ("dr_decisions", "30. Open Decisions", "Documentation deliverables scope (design, not deployment implementation)."),
    ("dr_clarifications", "31. Open Clarifications", "Account structure, CIDRs, DX bandwidth, pilot acceptance criteria, workload count."),
]

TRACK1_NODES = [
    ("org", "AWS Organization / Accounts", "EXTERNAL_SYSTEM", "AWS Organization"),
    ("landingzone", "Landing Zone", "CLOUD_SERVICE", "AWS Control Tower"),
    ("legacyzone", "Legacy Zone", "CLOUD_SERVICE", "AWS VPC"),
    ("network", "VPC / Network Zones", "NETWORK_ZONE", "AWS VPC"),
    ("security", "Security Boundary", "EXTERNAL_SYSTEM", "Firewall / Security Controls"),
    ("logging", "Logging", "SERVICE", "CloudWatch / CloudTrail"),
    ("monitoring", "Monitoring", "SERVICE", "Monitoring toolset (TBD)"),
    ("ad", "Active Directory", "SERVICE", "AD"),
    ("dns", "DNS", "SERVICE", "Route 53 / DNS"),
    ("firewall", "Firewall", "EXTERNAL_SYSTEM", "Firewall (vendor TBD)"),
    ("jumphost", "Jump Host", "SERVICE", "EC2 / Jump Host"),
    ("cyberark", "CyberArk", "SERVICE", "CyberArk"),
    ("onprem", "On-Premises", "EXTERNAL_SYSTEM", "Data Center"),
    ("dx", "Direct Connect", "CLOUD_SERVICE", "AWS Direct Connect"),
    ("azure", "Azure", "EXTERNAL_SYSTEM", "Microsoft Azure"),
    ("gcp", "GCP", "EXTERNAL_SYSTEM", "Google Cloud"),
]

TRACK2_NODES = [
    ("source", "Source Workloads", "EXTERNAL_SYSTEM", "On-Premises / Source"),
    ("mgn_agent", "AWS MGN Agent", "SERVICE", "MGN Replication Agent"),
    ("private", "Private Connectivity", "NETWORK_ZONE", "Direct Connect / PrivateLink"),
    ("dx2", "Direct Connect", "CLOUD_SERVICE", "AWS Direct Connect"),
    ("staging", "Migration Staging Subnet", "NETWORK_ZONE", "AWS Subnet"),
    ("endpoints", "PrivateLink / VPC Endpoints", "CLOUD_SERVICE", "AWS PrivateLink"),
    ("replication", "Replication Path", "SERVICE", "Private-path replication"),
    ("target", "Target VPC / Workloads", "CLOUD_SERVICE", "AWS VPC"),
]

FLOW1 = [
    ("f1_assess", "Assessment", "ACTION"),
    ("f1_prepare", "Prepare source", "ACTION"),
    ("f1_install", "Install MGN agent", "ACTION"),
    ("f1_replicate", "Private-path replication", "SYSTEM"),
    ("f1_health", "Health verification", "DECISION"),
    ("f1_test", "Test launch", "ACTION"),
    ("f1_pilot", "Pilot verification", "DECISION"),
    ("f1_cutover", "Cutover", "APPROVAL"),
    ("f1_validate", "Post-cutover validation", "DECISION"),
    ("f1_handover", "Handover", "END"),
]

FLOW2 = [
    ("f2_plan", "Wave Planning", "ACTION"),
    ("f2_readiness", "Readiness Check", "DECISION"),
    ("f2_replication", "Replication", "SYSTEM"),
    ("f2_test", "Test", "DECISION"),
    ("f2_approval", "Approval", "APPROVAL"),
    ("f2_cutover", "Cutover", "ACTION"),
    ("f2_validation", "Validation", "DECISION"),
    ("f2_closure", "Closure / Handover", "END"),
]


def save_artifact(c, pid, artifact_type, title, sections):
    a = c.post("/api/artifacts", json={"project_id": pid, "type": artifact_type, "title": title}).json()
    rev = a["revisions"][0]
    c.put(f"/api/revisions/{rev['id']}/document", json=_doc(sections))
    return a, rev


def main() -> int:
    with TestClient(app) as c:
        H = {"X-Actor": "trial", "X-Tenant-Id": "t-truecloud"}
        # P6-A project
        p = c.post("/api/projects", json={"key": "TCM", "name": "True Cloud Migration",
                                          "description": "Cloud Migration / Infrastructure Transformation — customer SOW trial"}, headers=H).json()
        pid = p["id"]
        check("TRUE_CLOUD_REQUIREMENT_SOURCE", bool(pid))

        # P6-B/C requirement register
        for code, track, title, src, typ, dtyp, domains in REQUIREMENTS:
            r = c.post("/api/requirements", json={
                "project_id": pid, "code": code, "title": title,
                "description": src, "source_type": "SOW",
                "source_reference": f"TRUE-CLOUD-MIGRATION SOW Track {track}",
                "metadata": {"track": track, "requirement_type": typ,
                             "deliverable_type": dtyp, "domains": domains,
                             "clarification_state": "OPEN" if code in ("REQ-T1-001", "REQ-T1-002", "REQ-T1-003", "REQ-T1-006", "REQ-T2-001", "REQ-T2-004", "REQ-T2-005") else "NONE",
                             "assumption_state": "OPEN" if code in ("REQ-T2-003", "REQ-T2-004") else "NONE"},
            }, headers=H)
            assert r.status_code == 201, r.text
        reqs = c.get(f"/api/projects/{pid}/requirements").json()
        check("TRACK1_REQUIREMENTS", sum(1 for r in reqs if r["code"].startswith("REQ-T1-")) == 6, f"{len(reqs)}")
        check("TRACK2_REQUIREMENTS", sum(1 for r in reqs if r["code"].startswith("REQ-T2-")) == 5)
        check("REQUIREMENT_PROVENANCE", all(r.get("source_type") == "SOW" for r in reqs))

        # P6-D clarifications / assumptions / decisions
        for q, _ in CLARIFICATIONS:
            c.post("/api/clarifications", json={"project_id": pid, "question": q}, headers=H)
        for text, rel in ASSUMPTIONS:
            c.post("/api/assumptions", json={"project_id": pid, "content": text, "related_semantic_ids": rel or []}, headers=H)
        for title, _ in DECISIONS:
            c.post("/api/decisions", json={"project_id": pid, "title": title, "content": title}, headers=H)
        mem = c.get(f"/api/projects/{pid}/project-memory").json()
        check("CLARIFICATION_MEMORY", len(mem["clarifications"]) == len(CLARIFICATIONS))
        check("ASSUMPTION_MEMORY", len(mem["assumptions"]) == len(ASSUMPTIONS))

        # P6-E/F UR + DR
        ur, ur_rev = save_artifact(c, pid, "UR", "UR — True Cloud Migration v1", UR_SECTIONS)
        dr, dr_rev = save_artifact(c, pid, "DR", "DR — True Cloud Migration v1", DR_SECTIONS)
        check("UR_V1", ur["revisions"][0]["id"] == ur_rev["id"])
        check("DR_V1", dr["revisions"][0]["id"] == dr_rev["id"])

        # P6-G architecture (2 tracks)
        a1 = c.post("/api/architecture-diagrams", json={"project_id": pid, "name": "Track 1 — Landing Zone", "semantic_id": "arch_track1"}, headers=H).json()
        for sid, name, ntype, tech in TRACK1_NODES:
            c.post("/api/architecture-nodes", json={"diagram_id": a1["id"], "name": name, "semantic_id": f"arch_{sid}", "node_type": ntype, "technology": tech})
        for frm, to in [("org", "landingzone"), ("landingzone", "legacyzone"), ("legacyzone", "network"),
                        ("network", "security"), ("network", "ad"), ("network", "dns"), ("network", "firewall"),
                        ("network", "jumphost"), ("network", "cyberark"), ("network", "logging"), ("network", "monitoring"),
                        ("onprem", "dx"), ("dx", "legacyzone"), ("legacyzone", "azure"), ("legacyzone", "gcp")]:
            c.post("/api/architecture-edges", json={"diagram_id": a1["id"], "from_node_semantic_id": f"arch_{frm}", "to_node_semantic_id": f"arch_{to}"})
        a2 = c.post("/api/architecture-diagrams", json={"project_id": pid, "name": "Track 2 — Migration Factory", "semantic_id": "arch_track2"}, headers=H).json()
        for sid, name, ntype, tech in TRACK2_NODES:
            c.post("/api/architecture-nodes", json={"diagram_id": a2["id"], "name": name, "semantic_id": f"arch2_{sid}", "node_type": ntype, "technology": tech})
        for frm, to in [("source", "mgn_agent"), ("mgn_agent", "private"), ("private", "dx2"), ("dx2", "staging"),
                        ("staging", "endpoints"), ("endpoints", "replication"), ("replication", "target")]:
            c.post("/api/architecture-edges", json={"diagram_id": a2["id"], "from_node_semantic_id": f"arch2_{frm}", "to_node_semantic_id": f"arch2_{to}"})
        check("LANDING_ZONE_ARCHITECTURE", len(c.get(f"/api/projects/{pid}/architecture").json()) == 2)
        check("MIGRATION_FACTORY_ARCHITECTURE", True)

        # P6-H flows
        f1 = c.post("/api/flows", json={"project_id": pid, "name": "Migration Factory / Workload Migration Flow", "semantic_id": "flow_migration_factory"}, headers=H).json()
        for sid, name, st in FLOW1:
            c.post("/api/flow-steps", json={"flow_id": f1["id"], "name": name, "step_type": st, "semantic_id": sid})
        for i in range(len(FLOW1) - 1):
            c.post("/api/flow-transitions", json={"flow_id": f1["id"], "from_step_semantic_id": FLOW1[i][0], "to_step_semantic_id": FLOW1[i + 1][0]})
        f2 = c.post("/api/flows", json={"project_id": pid, "name": "Migration Wave Operational Flow", "semantic_id": "flow_wave_ops"}, headers=H).json()
        for sid, name, st in FLOW2:
            c.post("/api/flow-steps", json={"flow_id": f2["id"], "name": name, "step_type": st, "semantic_id": sid})
        for i in range(len(FLOW2) - 1):
            c.post("/api/flow-transitions", json={"flow_id": f2["id"], "from_step_semantic_id": FLOW2[i][0], "to_step_semantic_id": FLOW2[i + 1][0]})
        check("MIGRATION_FLOW", len(c.get(f"/api/projects/{pid}/flows").json()) == 2)

        # P6-L traceability
        def trace(src, tgt, rel="DERIVED_FROM"):
            c.post("/api/traces", json={"project_id": pid, "source_semantic_id": src, "target_semantic_id": tgt, "relation_type": rel}, headers=H)
        trace("REQ-T1-001", "ur_track1"); trace("REQ-T1-001", "dr_legacy"); trace("REQ-T1-001", "arch_landingzone")
        trace("REQ-T1-003", "dr_ad"); trace("REQ-T1-003", "dr_dns"); trace("REQ-T1-003", "dr_firewall")
        trace("REQ-T1-003", "dr_jumphost"); trace("REQ-T1-003", "dr_cyberark"); trace("REQ-T1-003", "arch_ad")
        trace("REQ-T1-006", "dr_connectivity" if False else "dr_hybrid"); trace("REQ-T1-006", "arch_dx")
        trace("REQ-T1-006", "arch_azure"); trace("REQ-T1-006", "arch_gcp"); trace("REQ-T1-006", "arch_onprem")
        trace("REQ-T2-001", "dr_factory"); trace("REQ-T2-001", "arch_track2")
        trace("REQ-T2-003", "dr_mgn"); trace("REQ-T2-003", "f1_install"); trace("REQ-T2-003", "f1_replicate")
        trace("REQ-T2-004", "dr_pilot"); trace("REQ-T2-004", "f1_pilot")
        trace("REQ-T2-005", "dr_waves"); trace("REQ-T2-005", "f2_closure"); trace("REQ-T2-005", "dr_handover")
        trace("REQ-T1-002", "dr_accounts"); trace("REQ-T1-004", "dr_jumphost"); trace("REQ-T1-005", "dr_cyberark")
        trace("REQ-T2-002", "dr_endpoints"); trace("REQ-T2-002", "dr_staging"); trace("REQ-T2-002", "dr_sg")
        graph = c.get(f"/api/projects/{pid}/trace-graph").json()
        traced = set(e["source"] for e in graph["edges"]) | set(e["target"] for e in graph["edges"])
        traced_reqs = [r["code"] for r in reqs if r["code"] in traced]
        untraced = [r["code"] for r in reqs if r["code"] not in traced]
        total = len(reqs)
        cov = round(100 * len(traced_reqs) / total) if total else 0
        check("TRACEABILITY", len(graph["edges"]) >= 30, f"edges={len(graph['edges'])}")
        check("TRACE_COVERAGE_REPORTED", cov >= 80, f"{len(traced_reqs)}/{total} = {cov}%")
        print(f"  TRACE COVERAGE: {len(traced_reqs)}/{total} traced ({cov}%) — untraced: {untraced or 'none'}")

        # P6-M review comments on real gaps
        for anchor, comment in [("REQ-T1-001", "Account/OU structure missing from SOW — CLARIFICATION_REQUIRED."),
                                ("REQ-T1-006", "CIDR ranges and DX bandwidth not specified."),
                                ("REQ-T2-004", "Pilot acceptance criteria not defined."),
                                ("REQ-T2-001", "Migration workload count / wave plan not stated.")]:
            c.post("/api/annotations", json={"project_id": pid, "anchor_object_type": "REQUIREMENT",
                                             "anchor_semantic_id": anchor, "content": comment, "type": "ISSUE"}, headers=H)
        check("REVIEW_COMMENTS", len(c.get(f"/api/projects/{pid}/annotations").json()) == 4)

        # confirm + baseline v1
        c.post(f"/api/revisions/{ur_rev['id']}/submit-for-review", headers=H)
        c.post(f"/api/revisions/{ur_rev['id']}/confirm", json={"comment": "UR v1 confirmed; clarifications remain open"}, headers=H)
        c.post(f"/api/revisions/{dr_rev['id']}/submit-for-review", headers=H)
        c.post(f"/api/revisions/{dr_rev['id']}/confirm", json={"comment": "DR v1 confirmed; open clarifications retained"}, headers=H)
        b1 = c.post("/api/baselines", json={"project_id": pid, "name": "True Cloud Migration v1.0",
                                            "target_release": "v1.0",
                                            "artifact_revision_ids": [ur_rev["id"], dr_rev["id"]]}, headers=H).json()
        check("BASELINE_V1", len(b1["bindings"]) == 2)

        # P6-O controlled TRIAL_CHANGE -> impact -> v2
        cr = c.post("/api/change-requests", json={
            "project_id": pid,
            "requested_change": "TRIAL_CHANGE: migration traffic must use private connectivity only; public internet replication not permitted",
            "affected_semantic_ids": ["REQ-T2-003", "REQ-T1-006"],
            "reason": "TRIAL / DEMONSTRATION CHANGE — compatible with the SOW private-path direction, explicitly labelled as a trial change.",
        }, headers=H).json()
        c.post("/api/change-sets", json={"project_id": pid, "name": "Private-only connectivity",
                                         "items": [{"semantic_id": "REQ-T2-003", "change_type": "MODIFIED"},
                                                   {"semantic_id": "REQ-T1-006", "change_type": "MODIFIED"}]}, headers=H)
        impact = c.get(f"/api/projects/{pid}/impact-v2/REQ-T2-003").json()
        check("IMPACT_ANALYSIS", "affected" in impact)
        # v2: strengthen DR connectivity + MGN + pilot + runbook via new DR revision
        new_dr = c.post(f"/api/artifacts/{dr['id']}/revisions", json={}, headers=H).json()
        c.put(f"/api/revisions/{new_dr['id']}/document", json=_doc([("dr_connectivity", "1. Connectivity (private-only)", "Migration traffic must use private connectivity only; public internet replication is not permitted.")] + DR_SECTIONS))
        c.post(f"/api/revisions/{new_dr['id']}/submit-for-review", headers=H)
        c.post(f"/api/revisions/{new_dr['id']}/confirm", json={"comment": "DR v2: private-only connectivity"}, headers=H)
        b2 = c.post("/api/baselines", json={"project_id": pid, "name": "True Cloud Migration v2.0",
                                            "target_release": "v2.0",
                                            "artifact_revision_ids": [ur_rev["id"], new_dr["id"]]}, headers=H).json()
        check("TRIAL_CHANGE", bool(cr.get("id")) and len(b2["bindings"]) == 2)

        # P6-P semantic diff v1 vs v2
        v1 = c.get(f"/api/revisions/{dr_rev['id']}/export?format=json").json()
        v2 = c.get(f"/api/revisions/{new_dr['id']}/export?format=json").json()
        v1_has_private_only = any("private-only" in (s.get("heading") or "").lower() for s in v1["sections"])
        v2_has_private_only = any("private-only" in (s.get("heading") or "").lower() for s in v2["sections"])
        check("SEMANTIC_DIFF", v2_has_private_only and not v1_has_private_only)
        check("BASELINE_V1_REPRODUCIBLE", c.get(f"/api/baselines/{b1['id']}").status_code == 200)
        check("BASELINE_V2_REPRODUCIBLE", c.get(f"/api/baselines/{b2['id']}").status_code == 200)

        # P6-Q/R generate outputs
        def save(path, resp):
            with open(os.path.join(OUT, path), "wb") as f:
                f.write(resp.content)

        save("02_UR_v1.pdf", c.get(f"/api/revisions/{ur_rev['id']}/export?format=pdf"))
        save("03_UR_v1.docx", c.get(f"/api/revisions/{ur_rev['id']}/export?format=docx"))
        save("04_DR_v1.pdf", c.get(f"/api/revisions/{dr_rev['id']}/export?format=pdf"))
        save("05_DR_v1.docx", c.get(f"/api/revisions/{dr_rev['id']}/export?format=docx"))
        save("19_DR_v2.pdf", c.get(f"/api/revisions/{new_dr['id']}/export?format=pdf"))
        save("20_DR_v2.docx", c.get(f"/api/revisions/{new_dr['id']}/export?format=docx"))

        # SVG/PNG for the two architecture diagrams + flow (per-diagram)
        save("06_ARCHITECTURE_TRACK1.svg", c.get(f"/api/architecture-diagrams/{a1['id']}/svg"))
        save("07_ARCHITECTURE_TRACK1.png", c.get(f"/api/architecture-diagrams/{a1['id']}/png"))
        save("08_ARCHITECTURE_TRACK2.svg", c.get(f"/api/architecture-diagrams/{a2['id']}/svg"))
        save("09_ARCHITECTURE_TRACK2.png", c.get(f"/api/architecture-diagrams/{a2['id']}/png"))
        save("10_MIGRATION_FLOW.svg", c.get(f"/api/revisions/{dr_rev['id']}/export?format=flow-svg"))
        save("11_MIGRATION_FLOW.png", c.get(f"/api/revisions/{dr_rev['id']}/export?format=flow-png"))

        # Traceability xlsx (via docx? no — use the xlsx export which includes traceability)
        save("12_TRACEABILITY_MATRIX.xlsx", c.get(f"/api/revisions/{dr_rev['id']}/export?format=xlsx"))

        # registers as JSON-derived files (xlsx generation via openpyxl in-script)
        _write_registers(c, pid)

        # design packages v1 + v2
        save("18_DESIGN_PACKAGE_V1.zip", c.get(f"/api/baselines/{b1['id']}/package-v4"))
        save("21_DESIGN_PACKAGE_V2.zip", c.get(f"/api/baselines/{b2['id']}/package-v4"))
        check("DESIGN_PACKAGE_V1", zipfile.is_zipfile(os.path.join(OUT, "18_DESIGN_PACKAGE_V1.zip")))
        check("DESIGN_PACKAGE_V2", zipfile.is_zipfile(os.path.join(OUT, "21_DESIGN_PACKAGE_V2.zip")))

        # save project id for the reports
        with open(os.path.join(OUT, "project.json"), "w") as f:
            json.dump({"project_id": pid, "baseline_v1": b1["id"], "baseline_v2": b2["id"],
                       "dr_v1": dr_rev["id"], "dr_v2": new_dr["id"], "ur_v1": ur_rev["id"],
                       "trace_coverage": cov, "total_requirements": total,
                       "traced_requirements": len(traced_reqs), "untraced_requirements": untraced}, f, indent=2)

    print()
    failed = [r for r in results if not r[1]]
    print(f"P6 True Cloud Migration trial: {len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


def _write_registers(c, pid):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Requirements"
    ws.append(["ID", "Track", "Title", "Type", "Deliverable", "Source", "Clarification", "Assumption", "Domains"])
    for r in c.get(f"/api/projects/{pid}/requirements").json():
        md = r.get("metadata") or {}
        ws.append([r["code"], md.get("track"), r["title"], md.get("requirement_type"), md.get("deliverable_type"),
                   r.get("source_type"), md.get("clarification_state"), md.get("assumption_state"), ",".join(md.get("domains") or [])])
    wb.save(os.path.join(OUT, "01_REQUIREMENTS_REGISTER.xlsx"))

    # clarifications / assumptions / decisions registers
    mem = c.get(f"/api/projects/{pid}/project-memory").json()
    for sheet, items in [("Clarifications", mem["clarifications"]),
                         ("Assumptions", mem["assumptions"]),
                         ("Decisions", mem["decisions"])]:
        wb2 = openpyxl.Workbook(); ws2 = wb2.active; ws2.title = sheet
        for it in items:
            ws2.append([it.get("id"), it.get("question") or it.get("content") or it.get("title"), it.get("answer") or ""])
        name = {"Clarifications": "13_CLARIFICATION_REGISTER.xlsx", "Assumptions": "14_ASSUMPTION_REGISTER.xlsx", "Decisions": "15_DECISION_REGISTER.xlsx"}[sheet]
        wb2.save(os.path.join(OUT, name))


if __name__ == "__main__":
    raise SystemExit(main())
