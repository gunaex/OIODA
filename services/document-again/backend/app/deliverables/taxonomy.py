"""R17 — Universal Project Deliverable Standard Framework: taxonomies.

These are the controlled vocabularies for the deliverable framework. They are
pre-designed and must not be reduced to application-development documents.
"""

from __future__ import annotations

# ── Project Types ───────────────────────────────────────────────────────────
PROJECT_TYPES = [
    "APPLICATION_DEVELOPMENT",
    "APPLICATION_ENHANCEMENT",
    "INFRASTRUCTURE_IMPLEMENTATION",
    "CLOUD_IMPLEMENTATION",
    "CLOUD_MIGRATION",
    "DATA_PLATFORM",
    "DATA_MIGRATION",
    "DATA_GOVERNANCE",
    "ANALYTICS_BI",
    "AI_SOLUTION",
    "AI_RAG",
    "AI_AGENT",
    "SECURITY_IMPLEMENTATION",
    "SECURITY_ASSESSMENT",
    "NETWORK_IMPLEMENTATION",
    "CONNECTIVITY",
    "SYSTEM_INTEGRATION",
    "API_INTEGRATION",
    "PLATFORM_IMPLEMENTATION",
    "PACKAGE_IMPLEMENTATION",
    "UPGRADE_MODERNIZATION",
    "TECHNICAL_REFRESH",
    "POC_PILOT",
    "ASSESSMENT_CONSULTING",
    "OPERATIONS_TRANSITION",
    "MANAGED_SERVICE",
    "HYBRID_TRANSFORMATION",
    "OTHER",
]

# ── Workstreams ─────────────────────────────────────────────────────────────
WORKSTREAMS = [
    "PROJECT_MANAGEMENT",
    "BUSINESS_REQUIREMENT",
    "APPLICATION",
    "INTEGRATION",
    "DATA",
    "INFRASTRUCTURE",
    "CLOUD",
    "NETWORK",
    "SECURITY",
    "AI_RAG",
    "TESTING",
    "MIGRATION",
    "OPERATIONS",
    "TRAINING",
    "GOVERNANCE",
    "COMMERCIAL",
]

# ── Deliverable Categories ──────────────────────────────────────────────────
CATEGORIES = [
    "PROJECT_CONTROL",
    "REQUIREMENT",
    "ASSESSMENT",
    "DESIGN",
    "IMPLEMENTATION",
    "MIGRATION",
    "TEST",
    "SECURITY",
    "OPERATIONS",
    "GOVERNANCE",
    "COMMERCIAL",
    "ACCEPTANCE",
    "HANDOVER",
]

# ── Applicability states ────────────────────────────────────────────────────
APPLICABILITY_STATES = [
    "MANDATORY",
    "RECOMMENDED",
    "CONDITIONAL",
    "OPTIONAL",
    "NOT_APPLICABLE",
]

# ── Deliverable lifecycle states ────────────────────────────────────────────
LIFECYCLE_STATES = [
    "MISSING",
    "DRAFT",
    "INTERNAL_REVIEW",
    "CUSTOMER_REVIEW",
    "APPROVED",
    "BASELINED",
    "SUPERSEDED",
    "ARCHIVED",
]

# Valid lifecycle transitions (human-driven approval/baselining).
# AI may not transition into APPROVED or BASELINED.
LIFECYCLE_TRANSITIONS = {
    "MISSING": ["DRAFT"],
    "DRAFT": ["DRAFT", "INTERNAL_REVIEW", "ARCHIVED"],
    "INTERNAL_REVIEW": ["DRAFT", "CUSTOMER_REVIEW", "ARCHIVED"],
    "CUSTOMER_REVIEW": ["INTERNAL_REVIEW", "APPROVED", "ARCHIVED"],
    "APPROVED": ["BASELINED", "SUPERSEDED", "ARCHIVED"],
    "BASELINED": ["SUPERSEDED", "ARCHIVED"],
    "SUPERSEDED": ["ARCHIVED"],
    "ARCHIVED": [],
}

# States AI is never allowed to set.
HUMAN_ONLY_STATES = {"APPROVED", "BASELINED", "SUPERSEDED"}

# ── Project attributes (boolean flags) ──────────────────────────────────────
PROJECT_ATTRIBUTES = [
    "production_impact",
    "customer_facing",
    "regulated",
    "data_migration",
    "new_infrastructure",
    "third_party_integration",
    "disaster_recovery",
]

PRODUCTION_IMPACT_LEVELS = ["LOW", "MEDIUM", "HIGH"]

# ── Commercial value basis ──────────────────────────────────────────────────
COMMERCIAL_BASIS = [
    "ACTUAL",
    "CONTRACT_RATE",
    "CALCULATED",
    "AI_ESTIMATE",
    "MANUAL_INPUT",
    "UNKNOWN",
]

# ── Cell governance ─────────────────────────────────────────────────────────
CELL_GOVERNANCE = [
    "SYSTEM_GENERATED",
    "AUTHORITY_SYNCED",
    "CALCULATED",
    "HUMAN_INPUT",
    "LOCKED",
]

# ── Source authority service ids (bounded authorities) ──────────────────────
SOURCE_AUTHORITIES = [
    "DOCUMENT_AGAIN",
    "PM_AGAIN",
    "QA_AGAIN",
    "INFRA_AGAIN",
    "ACCOUNT_AGAIN",
    "CONDUCTOR_AGAIN",
]
