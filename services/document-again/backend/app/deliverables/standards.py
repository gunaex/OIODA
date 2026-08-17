"""R17 — Seeded Deliverable Standard Registry.

Each standard is a versioned, reusable definition. A standard is NOT the same
as a project deliverable instance (see service.py). Codes are generated
deterministically per domain; names carry the human meaning.
"""

from __future__ import annotations

from .taxonomy import APPLICABILITY_STATES, CATEGORIES, WORKSTREAMS

# (name, category, domain, workstreams, strength, attributes)
#   workstreams: workstreams whose presence activates this deliverable
#   strength:    MANDATORY or RECOMMENDED when activated
#   attributes:  project attribute keys that force MANDATORY
_STD = [
    # ── CORE (universal project governance — always applicable) ──────────
    ("Project Context / Charter", "PROJECT_CONTROL", "CORE", [], "MANDATORY", []),
    ("Scope / SOW Register", "PROJECT_CONTROL", "CORE", [], "MANDATORY", []),
    ("Stakeholder Register", "PROJECT_CONTROL", "CORE", [], "MANDATORY", []),
    ("Deliverable Register", "PROJECT_CONTROL", "CORE", [], "MANDATORY", []),
    ("Milestone Register", "PROJECT_CONTROL", "CORE", [], "MANDATORY", []),
    ("Requirement Register", "REQUIREMENT", "CORE", [], "MANDATORY", []),
    ("Traceability Matrix", "REQUIREMENT", "CORE", [], "MANDATORY", []),
    ("Clarification Register", "REQUIREMENT", "CORE", [], "MANDATORY", []),
    ("Assumption Register", "REQUIREMENT", "CORE", [], "MANDATORY", []),
    ("Decision Register", "REQUIREMENT", "CORE", [], "MANDATORY", []),
    ("Dependency Register", "REQUIREMENT", "CORE", [], "MANDATORY", []),
    ("RAID Register", "PROJECT_CONTROL", "CORE", [], "MANDATORY", []),
    ("Action / Issue Register", "PROJECT_CONTROL", "CORE", [], "MANDATORY", []),
    ("Change Request Register", "PROJECT_CONTROL", "CORE", [], "MANDATORY", []),
    ("Acceptance Register", "ACCEPTANCE", "CORE", [], "MANDATORY", []),
    ("Project Handover Summary", "HANDOVER", "CORE", [], "MANDATORY", []),

    # ── APPLICATION ────────────────────────────────────────────────────────
    ("Application Scope", "REQUIREMENT", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("User Requirement", "REQUIREMENT", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Functional Requirement", "REQUIREMENT", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Non-Functional Requirement", "REQUIREMENT", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Function List", "REQUIREMENT", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Application Architecture", "DESIGN", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Screen / UI Specification", "DESIGN", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("API Specification", "DESIGN", "APPLICATION", ["APPLICATION", "INTEGRATION"], "MANDATORY", []),
    ("Integration Specification", "DESIGN", "APPLICATION", ["APPLICATION", "INTEGRATION"], "MANDATORY", []),
    ("Data Model", "DESIGN", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Batch / Job Design", "DESIGN", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Error Handling Design", "DESIGN", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Deployment Design", "DESIGN", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Release Plan", "IMPLEMENTATION", "APPLICATION", ["APPLICATION"], "MANDATORY", []),
    ("Application Handover", "HANDOVER", "APPLICATION", ["APPLICATION"], "MANDATORY", []),

    # ── INFRASTRUCTURE ─────────────────────────────────────────────────────
    ("Infrastructure Assessment", "ASSESSMENT", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Current-State Architecture", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Target-State Architecture", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Infrastructure High-Level Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Infrastructure Low-Level Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Environment Matrix", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Server / Compute Inventory", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Storage Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Network Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE", "NETWORK"], "MANDATORY", []),
    ("Port / Firewall Matrix", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE", "NETWORK"], "MANDATORY", []),
    ("DNS / IP Plan", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE", "NETWORK"], "MANDATORY", []),
    ("Load Balancer Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE", "NETWORK"], "MANDATORY", []),
    ("Capacity / Sizing", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Availability Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Backup Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Disaster Recovery Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", ["disaster_recovery"]),
    ("Monitoring Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Logging Design", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Installation Plan", "IMPLEMENTATION", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Configuration Workbook", "IMPLEMENTATION", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Implementation Runbook", "IMPLEMENTATION", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Implementation Checklist", "IMPLEMENTATION", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Infrastructure Test Plan", "TEST", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Infrastructure Test Result", "TEST", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("As-Built Architecture", "DESIGN", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("As-Built Configuration", "HANDOVER", "INFRASTRUCTURE", ["INFRASTRUCTURE"], "MANDATORY", []),
    ("Operational Handover", "HANDOVER", "INFRASTRUCTURE", ["INFRASTRUCTURE", "OPERATIONS"], "MANDATORY", []),

    # ── CLOUD ──────────────────────────────────────────────────────────────
    ("Cloud Landing Zone Design", "DESIGN", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Account / Subscription Structure", "DESIGN", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Region Strategy", "DESIGN", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Cloud Network Topology", "DESIGN", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Cloud IAM Design", "DESIGN", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Resource Naming Standard", "GOVERNANCE", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Tagging Standard", "GOVERNANCE", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Cloud Security Baseline", "SECURITY", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Cloud Logging / Monitoring", "OPERATIONS", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Cloud Backup / DR", "OPERATIONS", "CLOUD", ["CLOUD"], "MANDATORY", ["disaster_recovery"]),
    ("Cloud Resource Inventory", "DESIGN", "CLOUD", ["CLOUD"], "MANDATORY", []),
    ("Cloud Cost Estimate", "COMMERCIAL", "CLOUD", ["CLOUD"], "RECOMMENDED", []),
    ("Cloud Cost Baseline", "COMMERCIAL", "CLOUD", ["CLOUD"], "RECOMMENDED", []),
    ("IaC Design", "DESIGN", "CLOUD", ["CLOUD"], "RECOMMENDED", []),
    ("Cloud Operational Model", "OPERATIONS", "CLOUD", ["CLOUD"], "MANDATORY", []),

    # ── NETWORK / CONNECTIVITY ─────────────────────────────────────────────
    ("Network Requirement", "REQUIREMENT", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("Current Network Assessment", "ASSESSMENT", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("Target Network Architecture", "DESIGN", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("IP Address Plan", "DESIGN", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("Subnet / VLAN Plan", "DESIGN", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("Routing Design", "DESIGN", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("Firewall Rule Matrix", "DESIGN", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("DNS Design", "DESIGN", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("VPN Design", "DESIGN", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("Direct Connect / ExpressRoute Design", "DESIGN", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("Connectivity Test Plan", "TEST", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("Failover Test", "TEST", "NETWORK", ["NETWORK"], "MANDATORY", []),
    ("Network As-Built", "HANDOVER", "NETWORK", ["NETWORK"], "MANDATORY", []),

    # ── MIGRATION ──────────────────────────────────────────────────────────
    ("Migration Assessment", "ASSESSMENT", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Source Inventory", "ASSESSMENT", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Target Inventory", "ASSESSMENT", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Dependency Map", "ASSESSMENT", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Migration Readiness", "ASSESSMENT", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Migration Strategy", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Migration Wave Plan", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Migration Schedule", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Migration Runbook", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Cutover Plan", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Rollback Plan", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Communication Plan", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Downtime Plan", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Validation Plan", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Reconciliation Plan", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", ["data_migration"]),
    ("Hypercare Plan", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Decommission Plan", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Migration Completion Report", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Application Compatibility Assessment", "ASSESSMENT", "MIGRATION", ["MIGRATION"], "RECOMMENDED", []),
    ("Configuration Mapping", "DESIGN", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Application Cutover Checklist", "MIGRATION", "MIGRATION", ["MIGRATION"], "RECOMMENDED", []),
    ("Data Mapping", "DESIGN", "MIGRATION", ["MIGRATION", "DATA"], "MANDATORY", ["data_migration"]),
    ("Transformation Rules", "DESIGN", "MIGRATION", ["MIGRATION", "DATA"], "MANDATORY", ["data_migration"]),
    ("Data Validation", "TEST", "MIGRATION", ["MIGRATION", "DATA"], "MANDATORY", ["data_migration"]),
    ("Data Reconciliation", "TEST", "MIGRATION", ["MIGRATION", "DATA"], "MANDATORY", ["data_migration"]),
    ("Server Mapping", "DESIGN", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Storage Migration", "MIGRATION", "MIGRATION", ["MIGRATION"], "MANDATORY", []),
    ("Network Cutover", "MIGRATION", "MIGRATION", ["MIGRATION", "NETWORK"], "MANDATORY", []),

    # ── SECURITY ───────────────────────────────────────────────────────────
    ("Security Requirement", "REQUIREMENT", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Security Architecture", "DESIGN", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Security Risk Assessment", "ASSESSMENT", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Threat Model", "ASSESSMENT", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Security IAM Design", "DESIGN", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Role / Access Matrix", "DESIGN", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Privileged Access Design", "DESIGN", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Encryption Requirement", "REQUIREMENT", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Key Management Design", "DESIGN", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Network Security Design", "DESIGN", "SECURITY", ["SECURITY", "NETWORK"], "MANDATORY", []),
    ("Security Hardening Checklist", "IMPLEMENTATION", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Security Configuration Baseline", "IMPLEMENTATION", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Compliance Mapping", "GOVERNANCE", "SECURITY", ["SECURITY"], "MANDATORY", ["regulated"]),
    ("VA Result", "TEST", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("PT Result", "TEST", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Vulnerability Register", "SECURITY", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Remediation Register", "SECURITY", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Security Test Plan", "TEST", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Security Acceptance", "ACCEPTANCE", "SECURITY", ["SECURITY"], "MANDATORY", []),
    ("Security Handover", "HANDOVER", "SECURITY", ["SECURITY"], "MANDATORY", []),

    # ── DATA ───────────────────────────────────────────────────────────────
    ("Data Requirement", "REQUIREMENT", "DATA", ["DATA"], "MANDATORY", ["data_migration"]),
    ("Source System Inventory", "ASSESSMENT", "DATA", ["DATA"], "MANDATORY", ["data_migration"]),
    ("Data Owner Register", "GOVERNANCE", "DATA", ["DATA"], "MANDATORY", []),
    ("Data Classification", "GOVERNANCE", "DATA", ["DATA"], "MANDATORY", []),
    ("Data Dictionary", "DESIGN", "DATA", ["DATA"], "MANDATORY", []),
    ("Logical Data Model", "DESIGN", "DATA", ["DATA"], "MANDATORY", []),
    ("Physical Data Model", "DESIGN", "DATA", ["DATA"], "MANDATORY", []),
    ("ETL / ELT Design", "DESIGN", "DATA", ["DATA"], "MANDATORY", ["data_migration"]),
    ("Pipeline Design", "DESIGN", "DATA", ["DATA"], "MANDATORY", []),
    ("Data Quality Rules", "GOVERNANCE", "DATA", ["DATA"], "MANDATORY", []),
    ("Data Quality Result", "TEST", "DATA", ["DATA"], "MANDATORY", []),
    ("Data Lineage", "GOVERNANCE", "DATA", ["DATA"], "MANDATORY", []),
    ("Retention / Archival", "GOVERNANCE", "DATA", ["DATA"], "RECOMMENDED", []),
    ("Data Migration Design", "MIGRATION", "DATA", ["DATA"], "MANDATORY", ["data_migration"]),
    ("Data Access Matrix", "GOVERNANCE", "DATA", ["DATA"], "MANDATORY", []),
    ("Data Governance Matrix", "GOVERNANCE", "DATA", ["DATA"], "MANDATORY", []),

    # ── AI / RAG ───────────────────────────────────────────────────────────
    ("AI Use Case Definition", "REQUIREMENT", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("AI Requirement", "REQUIREMENT", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("AI Risk Assessment", "ASSESSMENT", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Model / Provider Register", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Model Selection Record", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Knowledge Source Register", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Knowledge Governance", "GOVERNANCE", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("RAG Architecture", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Chunking Strategy", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Embedding Strategy", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Retrieval Strategy", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Prompt / Agent Design", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Tool / Function Register", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("AI Safety / Guardrail", "GOVERNANCE", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Content Governance", "GOVERNANCE", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Human-in-the-loop Design", "DESIGN", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("AI Evaluation Plan", "TEST", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Golden Dataset", "TEST", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Evaluation Result", "TEST", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Hallucination Test", "TEST", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Safety Test", "TEST", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Prompt Test", "TEST", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("Model / Prompt Version Register", "GOVERNANCE", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("AI Acceptance", "ACCEPTANCE", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("AI Operations / Monitoring", "OPERATIONS", "AI_RAG", ["AI_RAG"], "MANDATORY", []),
    ("AI Handover", "HANDOVER", "AI_RAG", ["AI_RAG"], "MANDATORY", []),

    # ── INTEGRATION ────────────────────────────────────────────────────────
    ("Integration Requirement", "REQUIREMENT", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Interface Inventory", "DESIGN", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Integration Architecture", "DESIGN", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Interface Control Document", "DESIGN", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Message / Payload Mapping", "DESIGN", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Field Mapping", "DESIGN", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Integration Authentication Design", "DESIGN", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Error / Retry Handling", "DESIGN", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Timeout Policy", "DESIGN", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Rate Limit", "DESIGN", "INTEGRATION", ["INTEGRATION"], "RECOMMENDED", ["third_party_integration"]),
    ("Integration Test", "TEST", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),
    ("Third-party Contact Register", "GOVERNANCE", "INTEGRATION", ["INTEGRATION"], "MANDATORY", ["third_party_integration"]),

    # ── TEST ───────────────────────────────────────────────────────────────
    ("Test Strategy", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Test Plan", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Test Scenario", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Test Case", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Test Data", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Test Execution Result", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Defect Register", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Regression Matrix", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Integration Test Result", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("System Test Result", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Performance Test Result", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Security Test Result", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("UAT Result", "TEST", "TEST", ["TESTING"], "MANDATORY", []),
    ("Acceptance Sign-off", "ACCEPTANCE", "TEST", ["TESTING"], "MANDATORY", []),

    # ── OPERATIONS ─────────────────────────────────────────────────────────
    ("Operational Model", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Support Model", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("RACI", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("SLA / SLO", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Monitoring Plan", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Alert Matrix", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Backup Procedure", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Restore Procedure", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("DR Procedure", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", ["disaster_recovery"]),
    ("Incident Procedure", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Problem Management", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Change Procedure", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Maintenance Plan", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Patch Plan", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Capacity Monitoring", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Known Error Register", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Operational Runbook", "OPERATIONS", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Knowledge Transfer", "HANDOVER", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),
    ("Operations Acceptance", "ACCEPTANCE", "OPERATIONS", ["OPERATIONS"], "MANDATORY", []),

    # ── COMMERCIAL ─────────────────────────────────────────────────────────
    ("BOM / BOQ", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "MANDATORY", []),
    ("Effort Estimate", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "MANDATORY", []),
    ("Cost Estimate", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "MANDATORY", []),
    ("Rate Card", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "MANDATORY", []),
    ("Cloud Cost", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "RECOMMENDED", []),
    ("License Cost", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "RECOMMENDED", []),
    ("Third-party Cost", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "RECOMMENDED", []),
    ("Recurring Cost", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "RECOMMENDED", []),
    ("One-time Cost", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "RECOMMENDED", []),
    ("Change Commercial Impact", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "CONDITIONAL", []),
    ("Commercial Assumption", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "CONDITIONAL", []),
    ("Commercial Baseline", "COMMERCIAL", "COMMERCIAL", ["COMMERCIAL"], "CONDITIONAL", []),
]

# Layout templates per category (defaults used when a standard has no explicit one)
CATEGORY_LAYOUT = {
    "PROJECT_CONTROL": "LAYOUT-REGISTER-001",
    "REQUIREMENT": "LAYOUT-REGISTER-001",
    "ASSESSMENT": "LAYOUT-REGISTER-001",
    "DESIGN": "LAYOUT-DESIGN-001",
    "IMPLEMENTATION": "LAYOUT-RUNBOOK-001",
    "MIGRATION": "LAYOUT-RUNBOOK-001",
    "TEST": "LAYOUT-TEST-001",
    "SECURITY": "LAYOUT-RISK-001",
    "OPERATIONS": "LAYOUT-RUNBOOK-001",
    "GOVERNANCE": "LAYOUT-MATRIX-001",
    "COMMERCIAL": "LAYOUT-REGISTER-001",
    "ACCEPTANCE": "LAYOUT-SIGNOFF-001",
    "HANDOVER": "LAYOUT-SIGNOFF-001",
}


def _build() -> dict[str, dict]:
    registry: dict[str, dict] = {}
    counters: dict[str, int] = {}
    for name, category, domain, workstreams, strength, attributes in _STD:
        counters[domain] = counters.get(domain, 0) + 1
        code = f"STD-{domain}-{counters[domain]:03d}"
        registry[code] = {
            "code": code,
            "name": name,
            "category": category,
            "domain": domain,
            "template_version": "1.0",
            "default_applicability": "CONDITIONAL" if domain != "CORE" else "MANDATORY",
            "workstreams": list(workstreams),
            "workstream_strength": strength,
            "attributes": list(attributes),
            "owner_role": "SOLUTION_ARCHITECT",
            "reviewer_roles": [],
            "approver_roles": ["CUSTOMER_TECHNICAL_OWNER"],
            "supported_exports": ["XLSX", "PDF"],
            "source_authorities": ["DOCUMENT_AGAIN"],
            "data_schema": f"{domain}_{category}_V1",
            "layout_template": CATEGORY_LAYOUT.get(category, "LAYOUT-REGISTER-001"),
            "lifecycle": [
                "DRAFT", "INTERNAL_REVIEW", "CUSTOMER_REVIEW",
                "APPROVED", "BASELINED", "SUPERSEDED",
            ],
        }
    return registry


STANDARDS = _build()


def all_standards() -> list[dict]:
    return list(STANDARDS.values())


def get_standard(code: str) -> dict | None:
    return STANDARDS.get(code)


def standards_by_domain() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for s in STANDARDS.values():
        out.setdefault(s["domain"], []).append(s)
    return out
