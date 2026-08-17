"""R17.1 — Human Deliverable Catalog, Composition Rules & Sign-off Gates.

The system keeps ~233 internal standards, but users see a SMALL catalog of
human deliverables composed from those standards (sections / registers /
annexes). This module is the static source of truth for:

  * the 3-level deliverable model (controlled / working / register)
  * the human deliverable catalog (HD-01 … HD-08 + domain HD-*)
  * section → internal-standard composition
  * project-type → human deliverable composition
  * role vocabulary + per-document sign-off policy
  * the 7 critical project sign-off gates

Nothing here is persisted to the DB; instances, sign-offs and audit events are
persisted in human_models.py / human.py.
"""

from __future__ import annotations

from .standards import STANDARDS

# ── 3-level model ───────────────────────────────────────────────────────────
LEVELS = {
    1: "CONTROLLED",   # people must understand / approve / accept
    2: "WORKING",      # delivery-team working documents
    3: "REGISTER",     # registers / annexes / evidence
}

# ── Roles ───────────────────────────────────────────────────────────────────
ROLES = [
    "PROJECT_MANAGER", "PROJECT_SPONSOR", "SOLUTION_ARCHITECT", "MIGRATION_LEAD",
    "INFRASTRUCTURE_LEAD", "APPLICATION_LEAD", "SECURITY_LEAD", "DATA_LEAD",
    "NETWORK_LEAD", "TEST_LEAD", "QA_LEAD", "OPERATIONS_LEAD",
    "CUSTOMER_TECHNICAL_OWNER", "BUSINESS_OWNER", "CUSTOMER_REPRESENTATIVE",
    "SERVICE_DELIVERY_MANAGER", "COMMERCIAL_OWNER",
]

# ── Critical project sign-off gates ─────────────────────────────────────────
# order is the sequential acceptance order across a project.
SIGN_OFF_GATES = [
    {"code": "SCOPE_ACCEPTANCE",    "name": "Scope / Requirement Acceptance", "order": 1, "phase": "DISCOVERY"},
    {"code": "DESIGN_ACCEPTANCE",   "name": "Design Acceptance",              "order": 2, "phase": "DESIGN"},
    {"code": "CHANGE_ACCEPTANCE",   "name": "Change Acceptance",              "order": 3, "phase": "ANY"},
    {"code": "TEST_UAT_ACCEPTANCE", "name": "Test / UAT Acceptance",          "order": 4, "phase": "TEST"},
    {"code": "GOLIVE_CUTOVER",      "name": "Go-Live / Cutover Approval",     "order": 5, "phase": "CUTOVER"},
    {"code": "HANDOVER_ACCEPTANCE", "name": "Handover Acceptance",            "order": 6, "phase": "HYPERCARE"},
    {"code": "FINAL_ACCEPTANCE",    "name": "Final Project Acceptance",       "order": 7, "phase": "CLOSURE"},
]
GATE_BY_CODE = {g["code"]: g for g in SIGN_OFF_GATES}

# Sequential project phase ordering (for timing / NOT_DUE computation).
PHASE_ORDER = ["INITIATION", "DISCOVERY", "DESIGN", "BUILD", "TEST", "MIGRATION_READINESS",
               "CUTOVER", "HYPERCARE", "CLOSURE"]


# ── Sign-off policy modes ───────────────────────────────────────────────────
SIGNOFF_MODES = ["REQUIRED", "CONDITIONAL", "NONE"]
SIGNOFF_DECISIONS = ["APPROVE", "ACCEPT", "ACKNOWLEDGE", "REJECT", "ACCEPTED_WITH_EXCEPTIONS"]
MATERIALITY_STATES = ["NON_MATERIAL_CHANGE", "MATERIAL_CHANGE", "UNKNOWN"]
FRESHNESS_STATES = ["CURRENT", "STALE", "UNKNOWN"]
READINESS_STATES = ["READY", "READY_WITH_GAPS", "NOT_READY", "BLOCKED", "NOT_DUE"]

# ── Section → internal standard mapping (name → authority + readiness key) ──
#   authority: which bounded service owns the authoritative truth
#   key:       deterministic source indicator computed from Document Again's
#              project truth (see human.py build_source_indicators)
_SOURCE_MAP = {}

def _reg(name, authority="DOCUMENT_AGAIN", key=None):
    _SOURCE_MAP[name] = {"authority": authority, "key": key or name}

# Registers / requirement truth — Document Again owns these
_reg("Project Context / Charter", key="project_context")
_reg("Scope / SOW Register", key="scope")
_reg("Stakeholder Register", key="stakeholders")
_reg("Milestone Register", key="milestones")
_reg("Deliverable Register", key="deliverables")
_reg("Requirement Register", key="requirements")
_reg("Traceability Matrix", key="trace_links")
_reg("Clarification Register", key="clarifications")
_reg("Assumption Register", key="assumptions")
_reg("Decision Register", key="decisions")
_reg("Dependency Register", key="dependencies")
_reg("RAID Register", key="raid")
_reg("Action / Issue Register", key="raid")
_reg("Change Request Register", key="change_requests")
_reg("Acceptance Register", key="acceptance")
_reg("Project Handover Summary", key="handover")
_reg("Functional Requirement", key="requirements")
_reg("Non-Functional Requirement", key="requirements")
_reg("User Requirement", key="requirements")
_reg("Application Scope", key="requirements")
_reg("Function List", key="functions")
_reg("Test Strategy", key="test_evidence", authority="QA_AGAIN")
_reg("Test Plan", key="test_evidence", authority="QA_AGAIN")
_reg("Test Scenario", key="test_evidence", authority="QA_AGAIN")
_reg("Test Case", key="test_evidence", authority="QA_AGAIN")
_reg("Test Data", key="test_evidence", authority="QA_AGAIN")
_reg("Test Execution Result", key="test_evidence", authority="QA_AGAIN")
_reg("Defect Register", key="test_evidence", authority="QA_AGAIN")
_reg("Regression Matrix", key="test_evidence", authority="QA_AGAIN")
_reg("Integration Test Result", key="test_evidence", authority="QA_AGAIN")
_reg("System Test Result", key="test_evidence", authority="QA_AGAIN")
_reg("Performance Test Result", key="test_evidence", authority="QA_AGAIN")
_reg("Security Test Result", key="test_evidence", authority="QA_AGAIN")
_reg("UAT Result", key="test_evidence", authority="QA_AGAIN")
_reg("Acceptance Sign-off", key="acceptance")

# Design truth — architecture diagrams (Infra/architecture)
for _n in ["Target-State Architecture", "Current-State Architecture",
           "Infrastructure High-Level Design", "Infrastructure Low-Level Design",
           "Application Architecture", "Integration Architecture", "RAG Architecture",
           "Network Design", "Storage Design", "Availability Design",
           "Backup Design", "Disaster Recovery Design", "Monitoring Design",
           "Cloud Landing Zone Design", "Security Architecture", "Data Model",
           "Logical Data Model", "Physical Data Model", "As-Built Architecture"]:
    _reg(_n, authority="INFRA_AGAIN", key="architecture")

# Migration strategy/plan truth — process flows
for _n in ["Migration Assessment", "Source Inventory", "Target Inventory",
           "Dependency Map", "Migration Readiness", "Migration Strategy",
           "Migration Wave Plan", "Migration Schedule", "Downtime Plan",
           "Validation Plan", "Reconciliation Plan", "Hypercare Plan",
           "Decommission Plan", "Communication Plan", "Cutover Plan",
           "Rollback Plan", "Migration Runbook", "Application Cutover Checklist",
           "Network Cutover", "Data Mapping", "Transformation Rules",
           "Data Validation", "Data Reconciliation", "Data Migration Design"]:
    _reg(_n, authority="PM_AGAIN", key="flows")

# Operations truth — operational runbook content
for _n in ["Operational Model", "Support Model", "RACI", "SLA / SLO",
           "Monitoring Plan", "Alert Matrix", "Backup Procedure", "Restore Procedure",
           "DR Procedure", "Incident Procedure", "Problem Management",
           "Change Procedure", "Maintenance Plan", "Patch Plan", "Capacity Monitoring",
           "Known Error Register", "Operational Runbook", "Knowledge Transfer",
           "Operations Acceptance", "Operational Handover", "Cloud Operational Model"]:
    _reg(_n, authority="DOCUMENT_AGAIN", key="operations")

# Security / governance
for _n in ["Security Requirement", "Security Risk Assessment", "Threat Model",
           "Security IAM Design", "Role / Access Matrix", "Privileged Access Design",
           "Encryption Requirement", "Key Management Design", "Network Security Design",
           "Security Hardening Checklist", "Security Configuration Baseline",
           "Compliance Mapping", "VA Result", "PT Result", "Vulnerability Register",
           "Remediation Register", "Security Test Plan", "Security Acceptance",
           "Security Handover"]:
    _reg(_n, authority="DOCUMENT_AGAIN", key="security")

# AI / RAG
for _n in ["AI Use Case Definition", "AI Requirement", "AI Risk Assessment",
           "Model / Provider Register", "Model Selection Record", "Knowledge Source Register",
           "Knowledge Governance", "Chunking Strategy", "Embedding Strategy",
           "Retrieval Strategy", "Prompt / Agent Design", "Tool / Function Register",
           "AI Safety / Guardrail", "Content Governance", "Human-in-the-loop Design",
           "AI Evaluation Plan", "Golden Dataset", "Evaluation Result",
           "Hallucination Test", "Safety Test", "Prompt Test",
           "Model / Prompt Version Register", "AI Acceptance", "AI Operations / Monitoring",
           "AI Handover"]:
    _reg(_n, authority="DOCUMENT_AGAIN", key="ai")

# Data
for _n in ["Data Requirement", "Source System Inventory", "Data Owner Register",
           "Data Classification", "Data Dictionary", "ETL / ELT Design",
           "Pipeline Design", "Data Quality Rules", "Data Quality Result",
           "Data Lineage", "Retention / Archival", "Data Access Matrix", "Data Governance Matrix"]:
    _reg(_n, authority="DOCUMENT_AGAIN", key="data")

# Infrastructure implementation / commercial / integration
for _n in ["Installation Plan", "Configuration Workbook", "Implementation Runbook",
           "Implementation Checklist", "Infrastructure Test Plan", "Infrastructure Test Result",
           "As-Built Configuration", "Environment Matrix", "Server / Compute Inventory",
           "Port / Firewall Matrix", "DNS / IP Plan", "Load Balancer Design",
           "Capacity / Sizing", "Logging Design", "Cloud Account / Subscription Structure",
           "Region Strategy", "Cloud Network Topology", "Cloud IAM Design",
           "Resource Naming Standard", "Tagging Standard", "Cloud Security Baseline",
           "Cloud Logging / Monitoring", "Cloud Backup / DR", "Cloud Resource Inventory",
           "IaC Design", "Cloud Cost Estimate", "Cloud Cost Baseline",
           "BOM / BOQ", "Effort Estimate", "Cost Estimate", "Rate Card",
           "Cloud Cost", "License Cost", "Third-party Cost", "Recurring Cost",
           "One-time Cost", "Change Commercial Impact", "Commercial Assumption",
           "Commercial Baseline", "Integration Requirement", "Interface Inventory",
           "Interface Control Document", "Message / Payload Mapping", "Field Mapping",
           "Integration Authentication Design", "Error / Retry Handling", "Timeout Policy",
           "Rate Limit", "Integration Test", "Third-party Contact Register",
           "Network Requirement", "Current Network Assessment", "Target Network Architecture",
           "IP Address Plan", "Subnet / VLAN Plan", "Routing Design", "Firewall Rule Matrix",
           "DNS Design", "VPN Design", "Direct Connect / ExpressRoute Design",
           "Connectivity Test Plan", "Failover Test", "Network As-Built",
           "Screen / UI Specification", "API Specification", "Integration Specification",
           "Batch / Job Design", "Error Handling Design", "Deployment Design", "Release Plan",
           "Application Handover", "Application Compatibility Assessment", "Configuration Mapping",
           "Server Mapping", "Storage Migration", "Infrastructure Assessment",
           "Migration Completion Report"]:
    _reg(_n, authority="DOCUMENT_AGAIN", key="generic")


def source_for(name: str) -> dict:
    return _SOURCE_MAP.get(name, {"authority": "DOCUMENT_AGAIN", "key": "generic"})


# ── Human deliverable catalog ───────────────────────────────────────────────
# Each entry composes sections; each section lists internal standard NAMES
# (resolved to STD codes at runtime via standards.by_name).
_H = []

def _hd(code, name, level, purpose, category, required_by, owner, reviewers,
        approvers, signatories, fyi, signoff_mode, sections):
    _H.append({
        "code": code, "name": name, "level": level, "purpose": purpose,
        "category": category, "required_by": required_by,
        "owner_role": owner, "reviewer_roles": reviewers, "approver_roles": approvers,
        "signatory_roles": signatories, "fyi_roles": fyi,
        "signoff_policy": {
            "mode": signoff_mode,
            "gate": required_by,
            "reapproval_on_material_change": True,
        },
        "sections": sections,
    })


def _s(title, standards, kind="section"):
    return {"title": title, "standards": standards, "kind": kind}


# ── Level 1 — Controlled / Approval documents ───────────────────────────────
_hd("HD-01", "Project Definition & Scope", 1,
    "Confirm what is being delivered, major exclusions, and shared understanding.",
    "PROJECT_CONTROL", "SCOPE_ACCEPTANCE",
    "PROJECT_MANAGER",
    ["SOLUTION_ARCHITECT", "CUSTOMER_TECHNICAL_OWNER"],
    ["BUSINESS_OWNER", "CUSTOMER_REPRESENTATIVE"],
    ["BUSINESS_OWNER", "CUSTOMER_REPRESENTATIVE"],
    ["PROJECT_SPONSOR", "OPERATIONS_LEAD"],
    "REQUIRED",
    [
        _s("Project Context", ["Project Context / Charter", "Scope / SOW Register"]),
        _s("Stakeholders", ["Stakeholder Register"]),
        _s("Requirements Overview", ["Requirement Register"]),
        _s("Clarifications", ["Clarification Register"], "register"),
        _s("Assumptions", ["Assumption Register"], "register"),
        _s("Decisions", ["Decision Register"], "register"),
        _s("Risks & Issues", ["RAID Register"], "register"),
    ])

_hd("HD-02", "Requirements & Solution Understanding", 1,
    "Consolidate requirements and confirm the customer's understanding of the solution need.",
    "REQUIREMENT", "SCOPE_ACCEPTANCE",
    "SOLUTION_ARCHITECT",
    ["APPLICATION_LEAD", "CUSTOMER_TECHNICAL_OWNER"],
    ["BUSINESS_OWNER"],
    ["BUSINESS_OWNER"],
    ["PROJECT_SPONSOR"],
    "CONDITIONAL",
    [
        _s("User Requirements", ["User Requirement", "Application Scope"]),
        _s("Functional Requirements", ["Functional Requirement", "Function List"]),
        _s("Non-Functional Requirements", ["Non-Functional Requirement"]),
        _s("Traceability", ["Traceability Matrix"], "register"),
        _s("Clarifications & Assumptions", ["Clarification Register", "Assumption Register"], "register"),
    ])

_hd("HD-03", "Solution / Target Design", 1,
    "Agree the target solution before implementation begins.",
    "DESIGN", "DESIGN_ACCEPTANCE",
    "SOLUTION_ARCHITECT",
    ["INFRASTRUCTURE_LEAD", "APPLICATION_LEAD", "SECURITY_LEAD"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["PROJECT_SPONSOR", "OPERATIONS_LEAD"],
    "REQUIRED",
    [
        _s("Target Architecture", ["Target-State Architecture", "Current-State Architecture"]),
        _s("Infrastructure Design", ["Infrastructure High-Level Design", "Availability Design", "Disaster Recovery Design"]),
        _s("Network & Connectivity", ["Network Design"]),
        _s("Application / Integration", ["Application Architecture", "Integration Architecture"]),
        _s("Cloud Foundation", ["Cloud Landing Zone Design"]),
    ])

_hd("HD-04", "Delivery / Implementation Plan", 1,
    "The agreed plan for building and deploying the solution.",
    "IMPLEMENTATION", "DESIGN_ACCEPTANCE",
    "PROJECT_MANAGER",
    ["INFRASTRUCTURE_LEAD", "APPLICATION_LEAD", "SECURITY_LEAD"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["SERVICE_DELIVERY_MANAGER"],
    ["PROJECT_SPONSOR"],
    "CONDITIONAL",
    [
        _s("Milestones & Dependencies", ["Milestone Register", "Dependency Register"], "register"),
        _s("Installation & Implementation", ["Installation Plan", "Implementation Runbook", "Implementation Checklist"]),
        _s("Release Plan", ["Release Plan"]),
        _s("Risks & Issues", ["RAID Register"], "register"),
    ])

_hd("HD-05", "Security, Risk & Compliance", 1,
    "Security posture, risk register and compliance mapping for the delivery.",
    "SECURITY", "DESIGN_ACCEPTANCE",
    "SECURITY_LEAD",
    ["INFRASTRUCTURE_LEAD", "APPLICATION_LEAD"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["CUSTOMER_TECHNICAL_OWNER", "SECURITY_LEAD"],
    ["PROJECT_SPONSOR"],
    "REQUIRED",
    [
        _s("Security Requirements", ["Security Requirement"]),
        _s("Security Architecture", ["Security Architecture", "Network Security Design"]),
        _s("Risk & Threat", ["Security Risk Assessment", "Threat Model"]),
        _s("Access Control", ["Role / Access Matrix", "Privileged Access Design"]),
        _s("Compliance", ["Compliance Mapping"]),
        _s("Vulnerabilities", ["Vulnerability Register", "Remediation Register"], "register"),
    ])

_hd("HD-06", "Test & Acceptance", 1,
    "Confirm agreed acceptance criteria were met, or known exceptions were accepted.",
    "TEST", "TEST_UAT_ACCEPTANCE",
    "TEST_LEAD",
    ["QA_LEAD", "APPLICATION_LEAD", "SECURITY_LEAD"],
    ["BUSINESS_OWNER", "CUSTOMER_REPRESENTATIVE"],
    ["BUSINESS_OWNER", "CUSTOMER_REPRESENTATIVE"],
    ["PROJECT_SPONSOR", "OPERATIONS_LEAD"],
    "REQUIRED",
    [
        _s("Test Strategy & Plan", ["Test Strategy", "Test Plan"]),
        _s("Test Cases", ["Test Case", "Test Scenario"], "register"),
        _s("Execution Results", ["Test Execution Result", "Defect Register"], "register"),
        _s("UAT", ["UAT Result"]),
        _s("Acceptance", ["Acceptance Sign-off"]),
    ])

_hd("HD-07", "Operations & Handover", 1,
    "Customer/Operations acknowledges system, documentation and knowledge transfer.",
    "OPERATIONS", "HANDOVER_ACCEPTANCE",
    "OPERATIONS_LEAD",
    ["INFRASTRUCTURE_LEAD", "APPLICATION_LEAD", "SECURITY_LEAD"],
    ["OPERATIONS_LEAD", "CUSTOMER_TECHNICAL_OWNER"],
    ["OPERATIONS_LEAD", "CUSTOMER_TECHNICAL_OWNER"],
    ["PROJECT_SPONSOR", "SERVICE_DELIVERY_MANAGER"],
    "REQUIRED",
    [
        _s("Operational Model", ["Operational Model", "Support Model", "RACI"]),
        _s("Service Levels", ["SLA / SLO", "Monitoring Plan", "Alert Matrix"]),
        _s("Backup / DR / Incident", ["Backup Procedure", "Restore Procedure", "DR Procedure", "Incident Procedure"]),
        _s("Knowledge Transfer", ["Knowledge Transfer", "Operational Handover"]),
        _s("Operations Acceptance", ["Operations Acceptance"]),
    ])

_hd("HD-08", "Project Closure & Final Acceptance", 1,
    "Confirm completion, or accepted outstanding items.",
    "ACCEPTANCE", "FINAL_ACCEPTANCE",
    "PROJECT_MANAGER",
    ["SOLUTION_ARCHITECT", "OPERATIONS_LEAD"],
    ["BUSINESS_OWNER", "PROJECT_SPONSOR"],
    ["BUSINESS_OWNER", "PROJECT_SPONSOR"],
    ["CUSTOMER_REPRESENTATIVE", "SERVICE_DELIVERY_MANAGER"],
    "REQUIRED",
    [
        _s("Acceptance Register", ["Acceptance Register"], "register"),
        _s("Handover Summary", ["Project Handover Summary"]),
        _s("Final Acceptance", ["Acceptance Sign-off"]),
        _s("Decisions & RAID", ["Decision Register", "RAID Register"], "register"),
    ])

# ── Level 2 — Working documents ─────────────────────────────────────────────
_hd("HD-INF-01", "Detailed Infrastructure Design", 2,
    "Low-level infrastructure design used by the delivery team.",
    "DESIGN", "DESIGN_ACCEPTANCE",
    "INFRASTRUCTURE_LEAD",
    ["SOLUTION_ARCHITECT", "SECURITY_LEAD", "NETWORK_LEAD"],
    ["SOLUTION_ARCHITECT"],
    [],
    ["OPERATIONS_LEAD"],
    "NONE",
    [
        _s("Low-Level Design", ["Infrastructure Low-Level Design", "Server / Compute Inventory"]),
        _s("Storage & Capacity", ["Storage Design", "Capacity / Sizing"]),
        _s("Network Detail", ["Network Design", "Port / Firewall Matrix", "DNS / IP Plan", "Load Balancer Design"]),
        _s("Backup & Monitoring", ["Backup Design", "Monitoring Design"]),
        _s("Environment Matrix", ["Environment Matrix"], "register"),
    ])

_hd("HD-APP-01", "Application Detailed Design", 2,
    "Detailed application design used by the delivery team.",
    "DESIGN", "DESIGN_ACCEPTANCE",
    "APPLICATION_LEAD",
    ["SOLUTION_ARCHITECT"],
    ["SOLUTION_ARCHITECT"],
    [],
    ["TEST_LEAD"],
    "NONE",
    [
        _s("Architecture", ["Application Architecture"]),
        _s("Function List", ["Function List"], "register"),
        _s("Screens & UI", ["Screen / UI Specification"]),
        _s("APIs & Integration", ["API Specification", "Integration Specification"]),
        _s("Data & Batch", ["Data Model", "Batch / Job Design"]),
        _s("Error Handling & Deployment", ["Error Handling Design", "Deployment Design"]),
    ])

_hd("HD-MIG-01", "Migration Strategy & Execution Plan", 1,
    "The agreed migration approach, wave plan and schedule.",
    "MIGRATION", "DESIGN_ACCEPTANCE",
    "MIGRATION_LEAD",
    ["INFRASTRUCTURE_LEAD", "APPLICATION_LEAD", "SECURITY_LEAD"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["PROJECT_SPONSOR", "OPERATIONS_LEAD"],
    "REQUIRED",
    [
        _s("Assessment & Inventories", ["Migration Assessment", "Source Inventory", "Target Inventory"]),
        _s("Dependencies & Readiness", ["Dependency Map", "Migration Readiness"]),
        _s("Migration Strategy", ["Migration Strategy"]),
        _s("Wave Plan & Schedule", ["Migration Wave Plan", "Migration Schedule"]),
        _s("Downtime & Communication", ["Downtime Plan", "Communication Plan"]),
        _s("Validation & Reconciliation", ["Validation Plan", "Reconciliation Plan"]),
        _s("Hypercare & Decommission", ["Hypercare Plan", "Decommission Plan"]),
    ])

_hd("HD-MIG-02", "Cutover & Rollback Runbook", 2,
    "Step-by-step cutover and rollback execution, owned by the delivery team.",
    "MIGRATION", "GOLIVE_CUTOVER",
    "MIGRATION_LEAD",
    ["INFRASTRUCTURE_LEAD", "APPLICATION_LEAD", "OPERATIONS_LEAD"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["PROJECT_SPONSOR", "OPERATIONS_LEAD"],
    "REQUIRED",
    [
        _s("Cutover Plan", ["Cutover Plan"]),
        _s("Runbook Steps", ["Migration Runbook", "Application Cutover Checklist", "Network Cutover"]),
        _s("Rollback", ["Rollback Plan"]),
        _s("Downtime & Communication", ["Downtime Plan", "Communication Plan"]),
        _s("Validation", ["Validation Plan"]),
    ])

_hd("HD-DATA-01", "Data Design & Migration", 2,
    "Data mapping, transformation and reconciliation for data-bearing projects.",
    "DATA", "DESIGN_ACCEPTANCE",
    "DATA_LEAD",
    ["SOLUTION_ARCHITECT", "APPLICATION_LEAD"],
    ["SOLUTION_ARCHITECT"],
    [],
    ["MIGRATION_LEAD"],
    "NONE",
    [
        _s("Data Requirements & Inventory", ["Data Requirement", "Source System Inventory"]),
        _s("Data Models", ["Data Dictionary", "Logical Data Model", "Physical Data Model"]),
        _s("Migration Mapping", ["Data Mapping", "Transformation Rules", "ETL / ELT Design"]),
        _s("Validation & Reconciliation", ["Data Validation", "Data Reconciliation"]),
        _s("Data Quality", ["Data Quality Rules"], "register"),
    ])

_hd("HD-AI-01", "AI / RAG Solution & Governance", 1,
    "AI/RAG solution design, evaluation and governance.",
    "AI_RAG", "DESIGN_ACCEPTANCE",
    "SOLUTION_ARCHITECT",
    ["SECURITY_LEAD", "DATA_LEAD"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["CUSTOMER_TECHNICAL_OWNER"],
    ["PROJECT_SPONSOR"],
    "CONDITIONAL",
    [
        _s("Use Case & Requirements", ["AI Use Case Definition", "AI Requirement"]),
        _s("Risk & Governance", ["AI Risk Assessment", "Knowledge Governance", "AI Safety / Guardrail"]),
        _s("RAG Architecture", ["RAG Architecture", "Chunking Strategy", "Embedding Strategy", "Retrieval Strategy"]),
        _s("Prompt / Agent", ["Prompt / Agent Design"]),
        _s("Evaluation", ["AI Evaluation Plan", "Golden Dataset", "Evaluation Result"]),
        _s("Operations & Acceptance", ["AI Operations / Monitoring", "AI Acceptance"]),
    ])

_hd("HD-SEC-01", "Security Assessment", 2,
    "Vulnerability, penetration and threat assessment evidence.",
    "SECURITY", "DESIGN_ACCEPTANCE",
    "SECURITY_LEAD",
    ["SOLUTION_ARCHITECT"],
    ["SECURITY_LEAD"],
    [],
    ["CUSTOMER_TECHNICAL_OWNER"],
    "NONE",
    [
        _s("Risk & Threat", ["Security Risk Assessment", "Threat Model"]),
        _s("VA / PT", ["VA Result", "PT Result"]),
        _s("Vulnerabilities", ["Vulnerability Register"], "register"),
        _s("Security Test Plan", ["Security Test Plan"]),
    ])

_hd("HD-OPS-01", "Operational Runbook", 2,
    "Day-2 operational runbook for the support team.",
    "OPERATIONS", "HANDOVER_ACCEPTANCE",
    "OPERATIONS_LEAD",
    ["INFRASTRUCTURE_LEAD", "APPLICATION_LEAD"],
    ["OPERATIONS_LEAD"],
    [],
    ["SERVICE_DELIVERY_MANAGER"],
    "NONE",
    [
        _s("Runbook", ["Operational Runbook"]),
        _s("Backup / Restore / DR", ["Backup Procedure", "Restore Procedure", "DR Procedure"]),
        _s("Incident & Change", ["Incident Procedure", "Change Procedure"]),
        _s("Monitoring & Patching", ["Monitoring Plan", "Alert Matrix", "Patch Plan", "Maintenance Plan"]),
    ])

HUMAN_DELIVERABLES = {h["code"]: h for h in _H}


# ── Supporting registers (level 3 — never formal controlled docs) ──────────
SUPPORTING_REGISTERS = [
    "Requirement Register", "Clarification Register", "Assumption Register",
    "Decision Register", "Change Request Register", "Traceability Matrix",
    "Environment Matrix", "Port / Firewall Matrix", "Risk Register",
    "Test Evidence", "RAID Register", "Dependency Register",
    "Stakeholder Register", "Milestone Register", "Acceptance Register",
]


# ── Project-type → human deliverable composition ────────────────────────────
# value: list of (human_code, applicability). CONDITIONAL entries are included
# only when a driving attribute is present (handled in compose_for_project).
_PROJECT_COMPOSITION = {
    "APPLICATION_DEVELOPMENT": [
        ("HD-01", "MANDATORY"), ("HD-02", "MANDATORY"), ("HD-APP-01", "MANDATORY"),
        ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "APPLICATION_ENHANCEMENT": [
        ("HD-01", "MANDATORY"), ("HD-02", "MANDATORY"), ("HD-APP-01", "RECOMMENDED"),
        ("HD-04", "MANDATORY"), ("HD-05", "RECOMMENDED"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "INFRASTRUCTURE_IMPLEMENTATION": [
        ("HD-01", "MANDATORY"), ("HD-03", "MANDATORY"), ("HD-INF-01", "MANDATORY"),
        ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "CLOUD_IMPLEMENTATION": [
        ("HD-01", "MANDATORY"), ("HD-03", "MANDATORY"), ("HD-INF-01", "MANDATORY"),
        ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "CLOUD_MIGRATION": [
        ("HD-01", "MANDATORY"), ("HD-03", "MANDATORY"), ("HD-INF-01", "MANDATORY"),
        ("HD-MIG-01", "MANDATORY"), ("HD-MIG-02", "MANDATORY"), ("HD-05", "MANDATORY"),
        ("HD-06", "MANDATORY"), ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
        ("HD-DATA-01", "CONDITIONAL"),
    ],
    "DATA_PLATFORM": [
        ("HD-01", "MANDATORY"), ("HD-02", "MANDATORY"), ("HD-DATA-01", "MANDATORY"),
        ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "DATA_MIGRATION": [
        ("HD-01", "MANDATORY"), ("HD-03", "MANDATORY"), ("HD-DATA-01", "MANDATORY"),
        ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "AI_SOLUTION": [
        ("HD-01", "MANDATORY"), ("HD-02", "MANDATORY"), ("HD-AI-01", "MANDATORY"),
        ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "AI_RAG": [
        ("HD-01", "MANDATORY"), ("HD-02", "MANDATORY"), ("HD-AI-01", "MANDATORY"),
        ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "AI_AGENT": [
        ("HD-01", "MANDATORY"), ("HD-02", "MANDATORY"), ("HD-AI-01", "MANDATORY"),
        ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "SECURITY_IMPLEMENTATION": [
        ("HD-01", "MANDATORY"), ("HD-03", "RECOMMENDED"), ("HD-SEC-01", "MANDATORY"),
        ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"), ("HD-07", "MANDATORY"),
        ("HD-08", "MANDATORY"),
    ],
    "SECURITY_ASSESSMENT": [
        ("HD-01", "MANDATORY"), ("HD-SEC-01", "MANDATORY"), ("HD-05", "MANDATORY"),
        ("HD-08", "MANDATORY"),
    ],
    "SYSTEM_INTEGRATION": [
        ("HD-01", "MANDATORY"), ("HD-02", "MANDATORY"), ("HD-03", "MANDATORY"),
        ("HD-APP-01", "RECOMMENDED"), ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"),
        ("HD-06", "MANDATORY"), ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "PLATFORM_IMPLEMENTATION": [
        ("HD-01", "MANDATORY"), ("HD-03", "MANDATORY"), ("HD-INF-01", "RECOMMENDED"),
        ("HD-04", "MANDATORY"), ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"),
        ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "POC_PILOT": [
        ("HD-01", "MANDATORY"), ("HD-02", "MANDATORY"), ("HD-04", "RECOMMENDED"),
        ("HD-06", "MANDATORY"), ("HD-08", "MANDATORY"),
    ],
    "HYBRID_TRANSFORMATION": [
        ("HD-01", "MANDATORY"), ("HD-02", "MANDATORY"), ("HD-03", "MANDATORY"),
        ("HD-MIG-01", "RECOMMENDED"), ("HD-MIG-02", "RECOMMENDED"), ("HD-DATA-01", "CONDITIONAL"),
        ("HD-05", "MANDATORY"), ("HD-06", "MANDATORY"), ("HD-07", "MANDATORY"),
        ("HD-08", "MANDATORY"),
    ],
    "OPERATIONS_TRANSITION": [
        ("HD-01", "MANDATORY"), ("HD-07", "MANDATORY"), ("HD-OPS-01", "MANDATORY"),
        ("HD-08", "MANDATORY"),
    ],
    "MANAGED_SERVICE": [
        ("HD-01", "MANDATORY"), ("HD-07", "MANDATORY"), ("HD-OPS-01", "MANDATORY"),
        ("HD-08", "MANDATORY"),
    ],
    "UPGRADE_MODERNIZATION": [
        ("HD-01", "MANDATORY"), ("HD-03", "MANDATORY"), ("HD-04", "MANDATORY"),
        ("HD-05", "RECOMMENDED"), ("HD-06", "MANDATORY"), ("HD-07", "MANDATORY"),
        ("HD-08", "MANDATORY"),
    ],
}

# fallback for any type not explicitly listed: a minimal universal set.
_FALLBACK_COMPOSITION = [
    ("HD-01", "MANDATORY"), ("HD-04", "MANDATORY"), ("HD-06", "MANDATORY"),
    ("HD-07", "MANDATORY"), ("HD-08", "MANDATORY"),
]

# conditional HDs driven by project attributes
_CONDITIONAL_DRIVER = {
    "HD-DATA-01": "data_migration",
}


def composition_for(primary_type: str) -> list[tuple[str, str]]:
    return list(_PROJECT_COMPOSITION.get(primary_type, _FALLBACK_COMPOSITION))
