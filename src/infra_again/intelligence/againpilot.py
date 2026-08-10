"""AGAINPILOT — AI Architecture Copilot.

Natural language → Canonical Architecture → draw.io.
Provider-abstracted architecture generation with deterministic fallback.

Phase C: AI_GENERATION_MODE defaults to DETERMINISTIC_FALLBACK until a real
LLM provider (LOCAL_LLM / OPENAI / CLAUDE / GEMINI) is configured.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================================
# Enums
# ============================================================================


class AIGenerationMode(str, Enum):
    REAL_LLM = "REAL_LLM"
    AI_CONTROL_CENTER = "AI_CONTROL_CENTER"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    UNAVAILABLE = "UNAVAILABLE"


class AIProvider(str, Enum):
    LOCAL_LLM = "LOCAL_LLM"
    OPENAI = "OPENAI"
    CLAUDE = "CLAUDE"
    GEMINI = "GEMINI"
    CLOUD_AI = "CLOUD_AI"
    NONE = "NONE"


class GenerationDepth(str, Enum):
    HIGH_LEVEL = "HIGH_LEVEL"
    DETAILED = "DETAILED"


class ProviderPreference(str, Enum):
    AUTO = "AUTO"
    AWS = "AWS"
    GCP = "GCP"
    ON_PREM = "ON_PREM"
    PRIVATE_CLOUD = "PRIVATE_CLOUD"


class PlatformPreference(str, Enum):
    AUTO = "AUTO"
    NATIVE_VM = "NATIVE_VM"
    KUBERNETES = "KUBERNETES"
    OPENSHIFT_OCP = "OPENSHIFT_OCP"
    BARE_METAL = "BARE_METAL"


class NodeSource(str, Enum):
    AI_GENERATED = "AI_GENERATED"
    USER_ADDED = "USER_ADDED"
    AI_REFINED = "AI_REFINED"
    IMPORTED = "IMPORTED"
    SYSTEM_GENERATED = "SYSTEM_GENERATED"


class ServiceVerification(str, Enum):
    SUPPORTED = "SUPPORTED"
    KNOWN_UNVERIFIED = "KNOWN_UNVERIFIED"
    UNKNOWN_SERVICE = "UNKNOWN_SERVICE"


# ============================================================================
# Schemas
# ============================================================================


@dataclass
class AgainPilotRequest:
    """Architecture generation request — natural language brief + structured hints."""
    brief: str

    provider_preference: ProviderPreference = ProviderPreference.AUTO
    platform_preference: PlatformPreference = PlatformPreference.AUTO
    generation_depth: GenerationDepth = GenerationDepth.HIGH_LEVEL

    constraints: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "brief": self.brief,
            "providerPreference": self.provider_preference.value,
            "platformPreference": self.platform_preference.value,
            "generationDepth": self.generation_depth.value,
            "constraints": self.constraints,
        }


@dataclass
class DetectedRequirement:
    provider: str
    platform: str
    expected_load: str
    availability: list[str]
    compliance: list[str]
    security: list[str]
    data_sensitivity: list[str]

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "platform": self.platform,
            "expectedLoad": self.expected_load,
            "availability": self.availability,
            "compliance": self.compliance,
            "security": self.security,
            "dataSensitivity": self.data_sensitivity,
        }


@dataclass
class GeneratedNode:
    node_id: str
    name: str
    category: str
    provider: str
    native_service: str
    platform: str
    security_zone: str
    data_classification: str
    owner: str
    source: str = "AI_GENERATED"
    verification_state: str = "UNVERIFIED"
    properties: dict = field(default_factory=dict)
    service_verification: str = "KNOWN_UNVERIFIED"

    def to_dict(self) -> dict:
        return {
            "nodeId": self.node_id,
            "name": self.name,
            "category": self.category,
            "provider": self.provider,
            "nativeService": self.native_service,
            "platform": self.platform,
            "securityZone": self.security_zone,
            "dataClassification": self.data_classification,
            "owner": self.owner,
            "source": self.source,
            "verificationState": self.verification_state,
            "properties": self.properties,
            "serviceVerification": self.service_verification,
        }


@dataclass
class GeneratedEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    protocol: str
    direction: str
    data_type: str
    security_classification: str
    label: str

    def to_dict(self) -> dict:
        return {
            "edgeId": self.edge_id,
            "sourceNodeId": self.source_node_id,
            "targetNodeId": self.target_node_id,
            "type": self.edge_type,
            "protocol": self.protocol,
            "direction": self.direction,
            "dataType": self.data_type,
            "securityClassification": self.security_classification,
            "label": self.label,
        }


@dataclass
class GeneratedGroup:
    group_id: str
    name: str
    group_type: str
    parent_group_id: str
    provider: str
    security_zone: str
    node_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "groupId": self.group_id,
            "name": self.name,
            "type": self.group_type,
            "parentGroupId": self.parent_group_id,
            "provider": self.provider,
            "securityZone": self.security_zone,
            "nodeIds": self.node_ids,
        }


@dataclass
class AgainPilotProposal:
    """Validated architecture proposal from AGAINPILOT generation."""
    title: str
    summary: str

    detected_requirements: DetectedRequirement

    nodes: list[GeneratedNode]
    edges: list[GeneratedEdge]
    groups: list[GeneratedGroup]

    views: dict[str, dict]

    native_service_recommendations: list[dict]

    assumptions: list[str]
    risks: list[str]
    clarifying_questions: list[str]

    rationale: str

    generation_provider: str = "DETERMINISTIC_FALLBACK"
    generation_model: str = "againpilot-v1"
    generation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    brief_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "detectedRequirements": self.detected_requirements.to_dict(),
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "groups": [g.to_dict() for g in self.groups],
            "views": self.views,
            "nativeServiceRecommendations": self.native_service_recommendations,
            "assumptions": self.assumptions,
            "risks": self.risks,
            "clarifyingQuestions": self.clarifying_questions,
            "rationale": self.rationale,
            "generationProvider": self.generation_provider,
            "generationModel": self.generation_model,
            "generationTimestamp": self.generation_timestamp,
            "briefHash": self.brief_hash,
        }


@dataclass
class RefineDelta:
    added_nodes: list[GeneratedNode] = field(default_factory=list)
    removed_nodes: list[str] = field(default_factory=list)
    changed_nodes: list[dict] = field(default_factory=list)
    added_edges: list[GeneratedEdge] = field(default_factory=list)
    removed_edges: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "addedNodes": [n.to_dict() for n in self.added_nodes],
            "removedNodes": self.removed_nodes,
            "changedNodes": self.changed_nodes,
            "addedEdges": [e.to_dict() for e in self.added_edges],
            "removedEdges": self.removed_edges,
            "summary": self.summary,
        }


@dataclass
class SecurityFinding:
    severity: str  # HIGH, MEDIUM, LOW, INFO
    title: str
    description: str
    recommendation: str

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
        }


@dataclass
class SecurityAnalysis:
    findings: list[SecurityFinding] = field(default_factory=list)
    missing_controls: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "missingControls": self.missing_controls,
            "risks": self.risks,
            "recommendations": self.recommendations,
        }


# ============================================================================
# Provider Catalog — Known services per provider
# ============================================================================

AWS_SERVICES: dict[str, dict] = {
    # User/Edge
    "route53":    {"category": "DNS", "description": "DNS and domain management"},
    "cloudfront": {"category": "NETWORK", "description": "Content delivery network"},
    "waf":        {"category": "SECURITY", "description": "Web application firewall"},
    "shield":     {"category": "SECURITY", "description": "DDoS protection"},
    # Networking
    "alb":        {"category": "NETWORK", "description": "Application load balancer"},
    "nlb":        {"category": "NETWORK", "description": "Network load balancer"},
    "api_gateway":{"category": "GATEWAY", "description": "API management gateway"},
    # Compute
    "ecs":        {"category": "APPLICATION", "description": "Container orchestration (ECS/Fargate)"},
    "eks":        {"category": "APPLICATION", "description": "Managed Kubernetes"},
    "lambda":     {"category": "APPLICATION", "description": "Serverless compute"},
    "ec2":        {"category": "APPLICATION", "description": "Virtual machines"},
    # Database
    "rds":        {"category": "DATABASE", "description": "Managed relational database"},
    "aurora":     {"category": "DATABASE", "description": "MySQL/PostgreSQL-compatible DB"},
    "dynamodb":   {"category": "DATABASE", "description": "NoSQL key-value/document store"},
    "elasticache":{"category": "CACHE", "description": "In-memory cache (Redis/Memcached)"},
    # Storage
    "s3":         {"category": "STORAGE", "description": "Object storage"},
    "efs":        {"category": "STORAGE", "description": "Elastic file system"},
    # Messaging
    "sqs":        {"category": "QUEUE", "description": "Message queue"},
    "sns":        {"category": "QUEUE", "description": "Pub/sub notification"},
    "eventbridge":{"category": "QUEUE", "description": "Event bus"},
    # Security
    "kms":        {"category": "SECURITY", "description": "Key management service"},
    "secrets_manager":{"category": "SECURITY", "description": "Secrets storage and rotation"},
    "acm":        {"category": "SECURITY", "description": "Certificate management"},
    "iam":        {"category": "SECURITY", "description": "Identity and access management"},
    "cognito":    {"category": "IDENTITY", "description": "User identity and authentication"},
    # Observability
    "cloudwatch": {"category": "OBSERVABILITY", "description": "Monitoring and observability"},
    "xray":       {"category": "OBSERVABILITY", "description": "Distributed tracing"},
}

GCP_SERVICES: dict[str, dict] = {
    "cloud_dns":     {"category": "DNS", "description": "DNS service"},
    "cloud_cdn":     {"category": "NETWORK", "description": "Content delivery"},
    "cloud_armor":   {"category": "SECURITY", "description": "WAF/DDoS protection"},
    "cloud_lb":      {"category": "NETWORK", "description": "Load balancing"},
    "api_gateway":   {"category": "GATEWAY", "description": "API gateway"},
    "cloud_run":     {"category": "APPLICATION", "description": "Serverless containers"},
    "gke":           {"category": "APPLICATION", "description": "Managed Kubernetes"},
    "compute_engine":{"category": "APPLICATION", "description": "Virtual machines"},
    "cloud_sql":     {"category": "DATABASE", "description": "Managed SQL database"},
    "bigquery":      {"category": "DATABASE", "description": "Analytics data warehouse"},
    "firestore":     {"category": "DATABASE", "description": "NoSQL document database"},
    "memorystore":   {"category": "CACHE", "description": "In-memory cache"},
    "cloud_storage": {"category": "STORAGE", "description": "Object storage"},
    "pubsub":        {"category": "QUEUE", "description": "Message queue"},
    "kms":           {"category": "SECURITY", "description": "Key management"},
    "secret_manager":{"category": "SECURITY", "description": "Secrets management"},
    "cloud_monitoring":{"category": "OBSERVABILITY", "description": "Monitoring"},
}

ON_PREM_SERVICES: dict[str, dict] = {
    "bind":         {"category": "DNS", "description": "DNS server"},
    "nginx":        {"category": "NETWORK", "description": "Reverse proxy / load balancer"},
    "haproxy":      {"category": "NETWORK", "description": "Load balancer"},
    "traefik":      {"category": "GATEWAY", "description": "API gateway / ingress"},
    "kubernetes":   {"category": "APPLICATION", "description": "Container orchestration"},
    "docker":       {"category": "APPLICATION", "description": "Container runtime"},
    "vault":        {"category": "SECURITY", "description": "Secrets management"},
    "postgresql":   {"category": "DATABASE", "description": "Relational database"},
    "mysql":        {"category": "DATABASE", "description": "Relational database"},
    "redis":        {"category": "CACHE", "description": "In-memory cache"},
    "minio":        {"category": "STORAGE", "description": "Object storage (S3-compatible)"},
    "rabbitmq":     {"category": "QUEUE", "description": "Message broker"},
    "prometheus":   {"category": "OBSERVABILITY", "description": "Monitoring"},
    "grafana":      {"category": "OBSERVABILITY", "description": "Visualization"},
    "keycloak":     {"category": "IDENTITY", "description": "Identity and SSO"},
    "openldap":     {"category": "IDENTITY", "description": "Directory services"},
}


def get_provider_catalog(provider: str) -> dict[str, dict]:
    p = provider.upper()
    if p == "AWS": return dict(AWS_SERVICES)
    if p == "GCP": return dict(GCP_SERVICES)
    return dict(ON_PREM_SERVICES)


def validate_service(provider: str, service_name: str) -> ServiceVerification:
    catalog = get_provider_catalog(provider)
    key = service_name.lower().replace(" ", "_").replace("-", "_")
    if key in catalog:
        return ServiceVerification.SUPPORTED
    # Partial match
    for k in catalog:
        if k in key or key in k:
            return ServiceVerification.KNOWN_UNVERIFIED
    return ServiceVerification.UNKNOWN_SERVICE


# ============================================================================
# Requirement Extraction
# ============================================================================


def extract_requirements(brief: str) -> DetectedRequirement:
    """Extract structured requirements from natural language brief using rules."""
    lower = brief.lower()

    # Provider detection
    provider = "ON_PREM"
    if re.search(r'\baws\b|amazon', lower): provider = "AWS"
    elif re.search(r'\bgcp\b|google cloud', lower): provider = "GCP"
    elif re.search(r'\bazure\b', lower): provider = "PRIVATE_CLOUD"
    elif re.search(r'\bon.prem|onprem|private cloud|bare metal', lower): provider = "ON_PREM"

    # Platform detection
    platform = "NATIVE_VM"
    if re.search(r'\bkubernetes\b|k8s|eks|gke|aks', lower): platform = "KUBERNETES"
    elif re.search(r'\bopenshift\b|ocp', lower): platform = "OPENSHIFT_OCP"
    elif re.search(r'\bcontainer|docker|fargate|cloud.run', lower): platform = "KUBERNETES"
    elif re.search(r'\bbare.metal|physical', lower): platform = "BARE_METAL"

    # Load detection
    expected_load = "UNKNOWN"
    load_match = re.search(r'(\d[\d,]*)\s*(users|requests|rps|qps)/?(day|second|min|hour)?', lower)
    if load_match:
        expected_load = load_match.group(0)

    # Availability
    availability: list[str] = []
    if re.search(r'\bha\b|high.availability|multi.az|multi.region', lower):
        availability.append("HIGH_AVAILABILITY")
    if re.search(r'\bdr\b|disaster.recovery', lower):
        availability.append("DISASTER_RECOVERY")
    if re.search(r'\b99\.9|sla', lower):
        availability.append("SLA_TARGETED")

    # Compliance
    compliance: list[str] = []
    if re.search(r'\bpdpa\b|personal.data|data.privacy', lower): compliance.append("PDPA")
    if re.search(r'\bgdpr\b', lower): compliance.append("GDPR")
    if re.search(r'\bhipaa\b', lower): compliance.append("HIPAA")
    if re.search(r'\bsoc2\b|soc.2', lower): compliance.append("SOC2")
    if re.search(r'\bpci\b|pci.dss', lower): compliance.append("PCI_DSS")

    # Security
    security: list[str] = []
    if re.search(r'\bprivate.db|private.database|no.public.db', lower):
        security.append("PRIVATE_DATABASE")
    if re.search(r'\bencrypt|tls|ssl', lower):
        security.append("ENCRYPTION_REQUIRED")
    if re.search(r'\bwaf|firewall', lower):
        security.append("WAF_FIREWALL")
    if re.search(r'\bsso|single.sign.on', lower):
        security.append("SSO")

    # Data sensitivity
    data_sensitivity: list[str] = []
    if re.search(r'\bpdpa\b|personal.data|patient|health|medical', lower):
        data_sensitivity.append("PERSONAL_DATA")
    if re.search(r'\bpii\b', lower):
        data_sensitivity.append("PII")
    if re.search(r'\bphi\b', lower):
        data_sensitivity.append("PHI")
    if re.search(r'\bfinancial|payment', lower):
        data_sensitivity.append("FINANCIAL")

    return DetectedRequirement(
        provider=provider,
        platform=platform,
        expected_load=expected_load,
        availability=availability,
        compliance=compliance,
        security=security,
        data_sensitivity=data_sensitivity,
    )


# ============================================================================
# Architecture Generation (Deterministic Fallback)
# ============================================================================


def _make_node(
    node_id: str, name: str, category: str, provider: str,
    native_service: str, platform: str = "NATIVE_VM",
    security_zone: str = "private", data_classification: str = "internal",
    owner: str = "", source: str = "AI_GENERATED",
) -> GeneratedNode:
    sv = validate_service(provider, native_service)
    return GeneratedNode(
        node_id=node_id, name=name, category=category,
        provider=provider, native_service=native_service, platform=platform,
        security_zone=security_zone, data_classification=data_classification,
        owner=owner, source=source,
        service_verification=sv.value,
    )


def generate_architecture(request: AgainPilotRequest) -> AgainPilotProposal:
    """Generate architecture proposal using deterministic rules.

    This is the DETERMINISTIC_FALLBACK implementation.
    Real LLM would be plugged in via AgainPilotProviderRouter.
    """
    req = extract_requirements(request.brief)
    provider = request.provider_preference.value if request.provider_preference != ProviderPreference.AUTO else req.provider
    platform = request.platform_preference.value if request.platform_preference != PlatformPreference.AUTO else req.platform

    nodes: list[GeneratedNode] = []
    edges: list[GeneratedEdge] = []
    groups: list[GeneratedGroup] = []
    recs: list[dict] = []
    assumptions: list[str] = []
    risks: list[str] = []
    questions: list[str] = []

    is_aws = provider == "AWS"
    is_gcp = provider == "GCP"
    is_ha = "HIGH_AVAILABILITY" in req.availability
    is_private_db = "PRIVATE_DATABASE" in req.security
    has_pdpa = "PDPA" in req.compliance
    is_container = platform in ("KUBERNETES", "OPENSHIFT_OCP")

    # ── Groups / Boundaries ──
    groups = [
        GeneratedGroup("GRP-INTERNET", "Internet", "PUBLIC", "", provider, "public"),
        GeneratedGroup("GRP-CLOUD", f"{provider} Cloud", "CLOUD", "", provider, "public"),
        GeneratedGroup("GRP-VPC", "VPC", "NETWORK", "GRP-CLOUD", provider, "private"),
        GeneratedGroup("GRP-PUB-SUBNET", "Public Subnets", "SUBNET", "GRP-VPC", provider, "dmz"),
        GeneratedGroup("GRP-APP-SUBNET", "Private Application Subnets", "SUBNET", "GRP-VPC", provider, "private"),
        GeneratedGroup("GRP-DATA-SUBNET", "Private Data Subnets", "SUBNET", "GRP-VPC", provider, "private"),
    ]

    # ── User / Entry ──
    nodes.append(_make_node("NODE-USER-001", "End User", "USER", provider, "", "WEB", "public", "none"))
    nodes.append(_make_node("NODE-DNS-001", "DNS", "DNS", provider, "route53" if is_aws else "cloud_dns" if is_gcp else "bind", "NATIVE_VM", "public", "none"))

    # ── Edge / CDN ──
    if is_aws:
        nodes.append(_make_node("NODE-CDN-001", "CloudFront CDN", "NETWORK", provider, "cloudfront", "NATIVE_VM", "public", "none"))
    elif is_gcp:
        nodes.append(_make_node("NODE-CDN-001", "Cloud CDN", "NETWORK", provider, "cloud_cdn", "NATIVE_VM", "public", "none"))

    # ── WAF / Security Edge ──
    nodes.append(_make_node("NODE-WAF-001", "WAF", "SECURITY", provider, "waf" if is_aws else "cloud_armor" if is_gcp else "nginx", "NATIVE_VM", "dmz", "none"))

    # ── Load Balancer ──
    nodes.append(_make_node("NODE-LB-001", "Application Load Balancer", "NETWORK", provider, "alb" if is_aws else "cloud_lb" if is_gcp else "haproxy", "NATIVE_VM", "dmz", "none"))

    # ── Application ──
    app_service = "ecs" if is_aws else "cloud_run" if is_gcp else "kubernetes"
    nodes.append(_make_node("NODE-APP-001", "Application Service", "APPLICATION", provider, app_service, platform, "private", "internal", "platform-team"))
    if is_ha:
        nodes.append(_make_node("NODE-APP-002", "Application Service (AZ2)", "APPLICATION", provider, app_service, platform, "private", "internal", "platform-team"))

    # ── Database ──
    db_service = "rds" if is_aws else "cloud_sql" if is_gcp else "postgresql"
    db_zone = "private"
    nodes.append(_make_node("NODE-DB-001", "Primary Database", "DATABASE", provider, db_service, "NATIVE_VM", db_zone, "pii" if has_pdpa else "internal", "data-team"))
    if is_ha:
        nodes.append(_make_node("NODE-DB-002", "Database Replica", "DATABASE", provider, db_service, "NATIVE_VM", "private", "pii" if has_pdpa else "internal", "data-team"))

    # ── Storage ──
    store_service = "s3" if is_aws else "cloud_storage" if is_gcp else "minio"
    nodes.append(_make_node("NODE-STORE-001", "Object Storage", "STORAGE", provider, store_service, "NATIVE_VM", "private", "internal"))

    # ── Cache ──
    if is_ha or request.generation_depth == GenerationDepth.DETAILED:
        nodes.append(_make_node("NODE-CACHE-001", "Cache", "CACHE", provider, "elasticache" if is_aws else "memorystore" if is_gcp else "redis", "NATIVE_VM", "private", "internal"))

    # ── Security / Secrets ──
    nodes.append(_make_node("NODE-KMS-001", "Key Management", "SECURITY", provider, "kms", "NATIVE_VM", "private", "internal", "security-team"))
    nodes.append(_make_node("NODE-SECRET-001", "Secrets Manager", "SECURITY", provider, "secrets_manager" if is_aws else "secret_manager" if is_gcp else "vault", "NATIVE_VM", "private", "internal", "security-team"))

    if has_pdpa:
        nodes.append(_make_node("NODE-AUTH-001", "Identity Provider", "IDENTITY", provider, "cognito" if is_aws else "keycloak", "NATIVE_VM", "private", "pii", "security-team"))

    # ── Observability ──
    nodes.append(_make_node("NODE-OBS-001", "Monitoring", "OBSERVABILITY", provider, "cloudwatch" if is_aws else "cloud_monitoring" if is_gcp else "prometheus", "NATIVE_VM", "private", "internal", "platform-team"))

    # ── Edges ──
    edge_idx = 0
    def add_edge(src: str, tgt: str, etype: str = "request", proto: str = "HTTPS",
                 direction: str = "unidirectional", dtype: str = "", sec: str = "none", lbl: str = ""):
        nonlocal edge_idx
        edge_idx += 1
        edges.append(GeneratedEdge(f"EDGE-{edge_idx:03d}", src, tgt, etype, proto, direction, dtype, sec, lbl or proto))

    add_edge("NODE-USER-001", "NODE-DNS-001", "request", "DNS", lbl="DNS")
    add_edge("NODE-DNS-001", "NODE-CDN-001", "request", "HTTPS", lbl="CDN")
    add_edge("NODE-CDN-001", "NODE-WAF-001", "request", "HTTPS", lbl="Inspect")
    add_edge("NODE-WAF-001", "NODE-LB-001", "request", "HTTPS", lbl="Forward")
    add_edge("NODE-LB-001", "NODE-APP-001", "request", "HTTP", lbl="Route")
    if is_ha:
        add_edge("NODE-LB-001", "NODE-APP-002", "request", "HTTP", lbl="Route")
    add_edge("NODE-APP-001", "NODE-DB-001", "data", "TCP", "bidirectional", "SQL", "pii", "SQL")
    if is_ha:
        add_edge("NODE-DB-001", "NODE-DB-002", "data", "TCP", "bidirectional", "SQL", "pii", "Replication")
    add_edge("NODE-APP-001", "NODE-STORE-001", "data", "HTTPS", "bidirectional", "blob", "internal", "Object API")
    add_edge("NODE-APP-001", "NODE-CACHE-001", "data", "TCP", "bidirectional", "cache", "internal", "Cache")
    add_edge("NODE-APP-001", "NODE-SECRET-001", "control", "HTTPS", lbl="Fetch Secrets")
    add_edge("NODE-APP-001", "NODE-OBS-001", "observation", "HTTPS", lbl="Metrics")
    add_edge("NODE-DB-001", "NODE-OBS-001", "observation", "HTTPS", lbl="DB Metrics")

    # ── Service Recommendations ──
    for n in nodes:
        if n.native_service:
            catalog = get_provider_catalog(provider)
            sv_key = n.native_service.lower().replace(" ", "_")
            desc = catalog.get(sv_key, {}).get("description", "")
            recs.append({
                "nodeId": n.node_id,
                "service": n.native_service,
                "category": n.category,
                "description": desc,
                "verification": n.service_verification,
                "rationale": f"Selected {n.native_service} for {n.name} ({n.category}) based on {provider} provider catalog",
            })

    # ── Assumptions ──
    assumptions = [
        f"Target provider: {provider}",
        f"Deployment platform: {platform}",
        "Private database access enforced" if is_private_db else "Database access via application tier",
        "High availability configured with multi-AZ deployment" if is_ha else "Single-AZ deployment",
        f"{'PDPA privacy considerations applied' if has_pdpa else 'Standard security controls'}",
        "HTTPS/TLS for all external traffic",
        "VPC with public/private subnet separation",
    ]

    # ── Risks ──
    risks = [
        "Service selection based on deterministic catalog — verify against actual requirements",
        "Load estimate from brief may need refinement with actual traffic data",
    ]
    if is_ha:
        risks.append("Multi-AZ adds cost — validate budget constraints")
    if has_pdpa:
        risks.append("PDPA compliance requires formal assessment beyond architectural design")
        risks.append("Data residency requirements may restrict region selection")

    # ── Questions ──
    questions = [
        "What is the expected data residency region?",
        "What is the budget constraint for HA infrastructure?",
        "Are there existing CI/CD pipelines to integrate?",
        "What authentication provider (SSO/SAML/OIDC) is preferred?",
    ]

    # ── Views ──
    all_node_ids = [n.node_id for n in nodes]
    all_edge_ids = [e.edge_id for e in edges]

    data_nodes = [n.node_id for n in nodes if n.category in ("DATABASE", "STORAGE", "CACHE", "QUEUE")]
    data_edges = [e.edge_id for e in edges if e.edge_type in ("data",)]

    ops_nodes = [n.node_id for n in nodes if n.category in ("USER", "DNS", "NETWORK", "GATEWAY", "APPLICATION")]
    ops_edges = [e.edge_id for e in edges if e.edge_type in ("request",)]

    sec_nodes = [n.node_id for n in nodes if n.category in ("SECURITY", "IDENTITY", "NETWORK")]
    sec_edges = [e.edge_id for e in edges if e.security_classification in ("pii",) or e.edge_type in ("control",)]

    views = {
        "architecture": {"nodes": all_node_ids, "edges": all_edge_ids},
        "dataFlow": {"nodes": data_nodes, "edges": data_edges},
        "operationFlow": {"nodes": ops_nodes, "edges": ops_edges},
        "securityFlow": {"nodes": sec_nodes, "edges": sec_edges},
    }

    # ── Rationale ──
    rationale_parts = [
        f"Provider: {provider} — selected based on brief",
        f"Platform: {platform} — {'containerized' if is_container else 'VM-based'} deployment",
        f"Load: {req.expected_load}",
        f"HA: {'Enabled (multi-AZ)' if is_ha else 'Single-AZ'}",
        f"Private DB: {'Enforced' if is_private_db else 'Application-tier access'}",
        f"Compliance: {', '.join(req.compliance) if req.compliance else 'Standard'}",
    ]

    brief_hash = hashlib.sha256(request.brief.encode()).hexdigest()[:12]

    return AgainPilotProposal(
        title=f"Architecture for {provider} {'Patient Portal' if 'patient' in request.brief.lower() else 'Application'}",
        summary=f"{provider} architecture with {len(nodes)} services. {'HA ' if is_ha else ''}{'PDPA ' if has_pdpa else ''}design.",
        detected_requirements=req,
        nodes=nodes,
        edges=edges,
        groups=groups,
        views=views,
        native_service_recommendations=recs,
        assumptions=assumptions,
        risks=risks,
        clarifying_questions=questions,
        rationale="\n".join(rationale_parts),
        generation_provider="DETERMINISTIC_FALLBACK",
        generation_model="againpilot-v1",
        brief_hash=brief_hash,
    )


# ============================================================================
# Refinement
# ============================================================================


def refine_architecture(
    current_nodes: list[dict],
    current_edges: list[dict],
    instruction: str,
    provider: str = "AWS",
) -> tuple[AgainPilotProposal, RefineDelta]:
    """Apply a refinement instruction to existing architecture.

    Deterministic fallback: parse instruction for keywords and apply changes.
    """
    lower = instruction.lower()
    added_nodes: list[GeneratedNode] = []
    removed_nodes: list[str] = []
    changed_nodes: list[dict] = []
    added_edges: list[GeneratedEdge] = []
    removed_edges: list[str] = []

    # Detect "Use X instead of Y" patterns
    replace_match = re.search(r'use\s+(\S+(?:\s+\S+)?)\s+(?:instead\s+of|for|as)\s+(\S+(?:\s+\S+)?)', lower)
    if replace_match:
        new_svc = replace_match.group(1).strip()
        old_svc = replace_match.group(2).strip()
        for n in current_nodes:
            if old_svc.lower() in n.get("nativeService", "").lower() or old_svc.lower() in n.get("name", "").lower():
                changed_nodes.append({"nodeId": n["nodeId"], "oldService": old_svc, "newService": new_svc, "change": "REPLACE_SERVICE"})

    # Detect "Add X"
    add_match = re.findall(r'add\s+(?:a\s+)?(\S+(?:\s+\S+)?(?:service|node|instance|cluster|replica|zone))', lower)
    for add_name in add_match:
        nid = f"NODE-ADD-{len(added_nodes)+1:03d}"
        added_nodes.append(_make_node(nid, add_name.title(), "APPLICATION", provider, add_name.lower().replace(" ", "_"), source="AI_REFINED"))

    # Detect "Remove X"
    remove_match = re.findall(r'remove\s+(\S+(?:\s+\S+)?)', lower)
    for rm_name in remove_match:
        for n in current_nodes:
            if rm_name.lower() in n.get("name", "").lower() or rm_name.lower() in n.get("nativeService", "").lower():
                removed_nodes.append(n["nodeId"])

    # Detect "no public route" / "private"
    if re.search(r'no\s+public|not?\s+public|private\s+(?:route|access)', lower):
        for e in current_edges:
            if e.get("securityClassification") != "pii":
                pass  # mark edges for review

    # Detect "separate X and Y into different private subnets"
    sep_match = re.search(r'separate\s+(\S+)\s+and\s+(\S+)\s+into\s+different', lower)
    if sep_match:
        changed_nodes.append({"change": "SUBNET_SEPARATION", "detail": f"Separate {sep_match.group(1)} and {sep_match.group(2)}"})

    delta = RefineDelta(
        added_nodes=added_nodes,
        removed_nodes=removed_nodes,
        changed_nodes=changed_nodes,
        added_edges=added_edges,
        removed_edges=removed_edges,
        summary=f"Refinement: {instruction[:80]}",
    )

    # Apply delta to create new proposal
    new_nodes = [n for n in current_nodes if n.get("nodeId") not in removed_nodes]
    # Add new nodes
    for an in added_nodes:
        new_nodes.append(an.to_dict())

    req = extract_requirements(instruction)
    proposal = AgainPilotProposal(
        title="Refined Architecture",
        summary=f"Refined: {instruction[:100]}",
        detected_requirements=req,
        nodes=[GeneratedNode(
            node_id=n.get("nodeId", ""), name=n.get("name", ""),
            category=n.get("category", "APPLICATION"), provider=n.get("provider", provider),
            native_service=n.get("nativeService", ""), platform=n.get("platform", "NATIVE_VM"),
            security_zone=n.get("securityZone", "private"),
            data_classification=n.get("dataClassification", "internal"),
            owner=n.get("owner", ""), source=n.get("source", "AI_REFINED"),
            verification_state=n.get("verificationState", "UNVERIFIED"),
            service_verification=n.get("serviceVerification", "KNOWN_UNVERIFIED"),
        ) for n in new_nodes],
        edges=[GeneratedEdge(
            edge_id=e.get("edgeId", ""), source_node_id=e.get("sourceNodeId", ""),
            target_node_id=e.get("targetNodeId", ""), edge_type=e.get("type", "request"),
            protocol=e.get("protocol", "TCP"), direction=e.get("direction", "unidirectional"),
            data_type=e.get("dataType", ""), security_classification=e.get("securityClassification", "none"),
            label=e.get("label", ""),
        ) for e in current_edges if e.get("edgeId") not in removed_edges],
        groups=[],
        views={"architecture": {"nodes": [], "edges": []}, "dataFlow": {"nodes": [], "edges": []},
               "operationFlow": {"nodes": [], "edges": []}, "securityFlow": {"nodes": [], "edges": []}},
        native_service_recommendations=[],
        assumptions=[], risks=[], clarifying_questions=[],
        rationale=f"Refinement applied: {instruction[:200]}",
        generation_provider="DETERMINISTIC_FALLBACK",
        generation_model="againpilot-v1-refine",
        brief_hash=hashlib.sha256(instruction.encode()).hexdigest()[:12],
    )

    return proposal, delta


def explain_architecture(nodes: list[dict], edges: list[dict], provider: str) -> str:
    """Generate explanatory text for the architecture."""
    cats = set(n.get("category", "") for n in nodes)
    svcs = [n.get("nativeService", "") for n in nodes if n.get("nativeService")]
    edge_types = set(e.get("type", "") for e in edges)
    has_ha = len([n for n in nodes if "AZ2" in n.get("nodeId", "") or "Replica" in n.get("name", "")]) > 0

    parts = [
        f"This {provider} architecture contains {len(nodes)} services across {len(cats)} categories.",
        f"Service categories: {', '.join(sorted(cats))}.",
    ]
    if svcs:
        parts.append(f"Provider-native services: {', '.join(svcs[:10])}.")
    parts.append(f"{len(edges)} connections with types: {', '.join(sorted(edge_types))}.")
    if has_ha:
        parts.append("High Availability: Multi-AZ deployment with redundant application and database instances.")
    parts.append("Network: Public subnets for edge services (DNS, CDN, WAF, LB), private subnets for applications and data.")
    parts.append("Security: WAF inspection at edge, TLS encryption for external traffic, secrets stored in managed secrets service.")

    return "\n\n".join(parts)


def analyze_security(nodes: list[dict], edges: list[dict], req: DetectedRequirement) -> SecurityAnalysis:
    """Analyze security posture of the architecture."""
    findings: list[SecurityFinding] = []
    missing: list[str] = []
    recs: list[str] = []

    has_waf = any(n.get("category") == "SECURITY" and "waf" in n.get("nativeService", "").lower() for n in nodes)
    has_kms = any("kms" in n.get("nativeService", "").lower() for n in nodes)
    has_secrets = any("secret" in n.get("nativeService", "").lower() or "vault" in n.get("nativeService", "").lower() for n in nodes)
    has_auth = any(n.get("category") == "IDENTITY" for n in nodes)
    has_db = any(n.get("category") == "DATABASE" for n in nodes)

    # Check for public DB route
    public_db_edge = [e for e in edges if
                      any(n.get("category") == "DATABASE" and n.get("nodeId") == e.get("targetNodeId") for n in nodes)
                      and e.get("securityClassification") != "pii"]
    if public_db_edge:
        findings.append(SecurityFinding("HIGH", "Database exposed to public route",
            "Database appears reachable from non-private path", "Move database to private subnet, restrict access to application tier only"))
    else:
        findings.append(SecurityFinding("INFO", "Database in private subnet", "Database access restricted", "No action needed"))

    if not has_waf:
        findings.append(SecurityFinding("MEDIUM", "No WAF detected", "Web application firewall not explicitly modeled", "Add WAF or cloud-native equivalent at the edge"))
        missing.append("WAF")

    if not has_kms:
        findings.append(SecurityFinding("MEDIUM", "No key management service", "Encryption keys not explicitly managed", "Add KMS or equivalent key management"))
        missing.append("KMS")

    if not has_secrets:
        findings.append(SecurityFinding("MEDIUM", "No secrets manager", "Application secrets not explicitly managed", "Add secrets manager or vault"))
        missing.append("SECRETS_MANAGER")

    if "PDPA" in req.compliance and not has_auth:
        findings.append(SecurityFinding("HIGH", "PDPA: No identity provider", "Patient data requires authentication controls", "Add identity provider (Cognito/Keycloak)"))
        missing.append("IDENTITY_PROVIDER")

    if has_db:
        findings.append(SecurityFinding("INFO", "Encryption at rest", "Verify database encryption at rest is enabled", "Enable RDS encryption / PostgreSQL TDE"))

    recs = [
        "Ensure all external traffic uses TLS 1.2+",
        "Implement least-privilege IAM policies",
        "Enable audit logging on all data stores",
        "Regular vulnerability scanning of container images",
    ]
    if "PDPA" in req.compliance:
        recs.append("PDPA: Conduct Data Protection Impact Assessment (DPIA)")
        recs.append("PDPA: Implement data retention and deletion policies")

    return SecurityAnalysis(findings=findings, missing_controls=missing, risks=[], recommendations=recs)


# ============================================================================
# Provider Router
# ============================================================================


class AgainPilotProviderRouter:
    """Routes architecture generation to the configured AI provider.

    Current implementation: DETERMINISTIC_FALLBACK only.
    Future: LOCAL_LLM (Ollama), OPENAI, CLAUDE, GEMINI, CLOUD_AI.
    """

    def __init__(self):
        self._mode = AIGenerationMode.DETERMINISTIC_FALLBACK
        self._provider = AIProvider.NONE

    @property
    def mode(self) -> AIGenerationMode:
        return self._mode

    @property
    def provider_name(self) -> str:
        return self._provider.value

    def generate(self, request: AgainPilotRequest) -> AgainPilotProposal:
        if self._mode == AIGenerationMode.DETERMINISTIC_FALLBACK:
            return generate_architecture(request)
        if self._mode == AIGenerationMode.UNAVAILABLE:
            raise RuntimeError("AI generation unavailable — no provider configured")
        # Future: route to LOCAL_LLM, OPENAI, etc.
        return generate_architecture(request)

    def refine(self, nodes: list[dict], edges: list[dict], instruction: str, provider: str = "AWS") -> tuple[AgainPilotProposal, RefineDelta]:
        return refine_architecture(nodes, edges, instruction, provider)

    def explain(self, nodes: list[dict], edges: list[dict], provider: str) -> str:
        return explain_architecture(nodes, edges, provider)

    def analyze_security(self, nodes: list[dict], edges: list[dict], req: DetectedRequirement) -> SecurityAnalysis:
        return analyze_security(nodes, edges, req)


# Singleton
_againpilot = AgainPilotProviderRouter()


def get_againpilot() -> AgainPilotProviderRouter:
    return _againpilot
