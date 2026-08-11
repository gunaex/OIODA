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


class ArchitecturePattern(str, Enum):
    INTERNET_FACING_WEB_APP = "INTERNET_FACING_WEB_APP"
    INTERNET_FACING_MULTI_AZ_WEB_APPLICATION = "INTERNET_FACING_MULTI_AZ_WEB_APPLICATION"
    INTERNAL_ENTERPRISE_APP = "INTERNAL_ENTERPRISE_APP"
    EVENT_DRIVEN_PLATFORM = "EVENT_DRIVEN_PLATFORM"
    DATA_PLATFORM = "DATA_PLATFORM"
    BATCH_PROCESSING = "BATCH_PROCESSING"
    MICROSERVICES = "MICROSERVICES"
    THREE_TIER_APPLICATION = "THREE_TIER_APPLICATION"


class TopologyZone(str, Enum):
    CLOUD_BOUNDARY = "CLOUD_BOUNDARY"
    NETWORK_BOUNDARY = "NETWORK_BOUNDARY"
    SUBNET_GROUP = "SUBNET_GROUP"
    AVAILABILITY_ZONE = "AVAILABILITY_ZONE"
    SECURITY_ZONE = "SECURITY_ZONE"
    EXTERNAL_SYSTEM = "EXTERNAL_SYSTEM"


class EdgeType(str, Enum):
    REQUEST = "request"
    DATA = "data"
    AUTH = "auth"
    SECRET_ACCESS = "secret_access"
    KEY_USAGE = "key_usage"
    TELEMETRY = "telemetry"
    CONTROL = "control"


class QualityResult(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


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
# Provider-Native Naming
# ============================================================================

# Maps internal service keys to display names per provider
PROVIDER_DISPLAY_NAMES: dict[str, dict[str, str]] = {
    "AWS": {
        "route53": "Route 53", "cloudfront": "CloudFront", "waf": "AWS WAF",
        "shield": "AWS Shield", "alb": "Application Load Balancer",
        "nlb": "Network Load Balancer", "api_gateway": "API Gateway",
        "ecs": "ECS Fargate", "eks": "EKS", "lambda": "Lambda",
        "ec2": "EC2", "rds": "Amazon RDS", "aurora": "Aurora",
        "dynamodb": "DynamoDB", "elasticache": "ElastiCache",
        "s3": "Amazon S3", "efs": "EFS", "sqs": "SQS", "sns": "SNS",
        "eventbridge": "EventBridge", "kms": "AWS KMS",
        "secrets_manager": "Secrets Manager", "acm": "Certificate Manager",
        "iam": "IAM", "cognito": "Amazon Cognito",
        "cloudwatch": "CloudWatch", "xray": "X-Ray",
    },
    "GCP": {
        "cloud_dns": "Cloud DNS", "cloud_cdn": "Cloud CDN",
        "cloud_armor": "Cloud Armor", "cloud_lb": "Cloud Load Balancer",
        "api_gateway": "API Gateway", "cloud_run": "Cloud Run",
        "gke": "GKE", "compute_engine": "Compute Engine",
        "cloud_sql": "Cloud SQL", "bigquery": "BigQuery",
        "firestore": "Firestore", "memorystore": "Memorystore",
        "cloud_storage": "Cloud Storage", "pubsub": "Pub/Sub",
        "kms": "Cloud KMS", "secret_manager": "Secret Manager",
        "cloud_monitoring": "Cloud Monitoring",
    },
    "ON_PREM": {
        "bind": "BIND DNS", "nginx": "NGINX", "haproxy": "HAProxy",
        "traefik": "Traefik", "kubernetes": "Kubernetes", "docker": "Docker",
        "vault": "HashiCorp Vault", "postgresql": "PostgreSQL",
        "mysql": "MySQL", "redis": "Redis", "minio": "MinIO",
        "rabbitmq": "RabbitMQ", "prometheus": "Prometheus", "grafana": "Grafana",
        "keycloak": "Keycloak", "openldap": "OpenLDAP",
    },
}

def get_display_name(provider: str, service_key: str) -> str:
    """Return provider-native display name for a service key."""
    key = service_key.lower().replace(" ", "_").replace("-", "_")
    names = PROVIDER_DISPLAY_NAMES.get(provider.upper(), {})
    return names.get(key, service_key)


# ============================================================================
# Architecture Quality Validator
# ============================================================================

@dataclass
class QualityReport:
    checks: list[dict] = field(default_factory=list)
    overall: QualityResult = QualityResult.PASS

    def add(self, gate: str, result: QualityResult, detail: str = ""):
        self.checks.append({"gate": gate, "result": result.value, "detail": detail})
        if result == QualityResult.FAIL:
            self.overall = QualityResult.FAIL
        elif result == QualityResult.WARN and self.overall != QualityResult.FAIL:
            self.overall = QualityResult.WARN

    def to_dict(self) -> dict:
        return {
            "overall": self.overall.value,
            "checks": self.checks,
        }


def validate_architecture_quality(
    nodes: list[dict], edges: list[dict], groups: list[dict],
    provider: str, req: DetectedRequirement, pattern: str,
) -> QualityReport:
    """Run all architecture quality checks."""
    report = QualityReport()
    node_ids = {n.get("nodeId", "") for n in nodes}
    edge_ids = {e.get("edgeId", "") for e in edges}

    # Provider consistency (exclude EXTERNAL category)
    non_external = [n for n in nodes if n.get("category") not in ("USER", "EXTERNAL") and n.get("provider", "")]
    provider_mismatch = [
        n.get("nodeId") for n in non_external
        if n.get("provider", "").upper() != provider.upper()
        and n.get("provider", "").upper() not in ("EXTERNAL", "")
    ]
    report.add("PROVIDER_CONSISTENCY",
        QualityResult.FAIL if provider_mismatch else QualityResult.PASS,
        f"Mismatched: {provider_mismatch}" if provider_mismatch else f"All nodes use {provider}")

    # Duplicate services (allow HA duplicates: same service, different AZ)
    svc_counts: dict[str, list[str]] = {}
    for n in nodes:
        svc = n.get("nativeService", "")
        if svc:
            svc_counts.setdefault(svc, []).append(n.get("nodeId", ""))
    # Allow up to 2 instances of the same service (primary+standby or AZ-A+AZ-B)
    dupes = {k: v for k, v in svc_counts.items() if len(v) > 2}
    report.add("DUPLICATE_SERVICES",
        QualityResult.FAIL if dupes else QualityResult.PASS,
        f"Duplicates >2: {list(dupes.keys())}" if dupes else "No excessive duplicates")

    # HA check (look for multi-AZ patterns: AZ-B in name or >1 app/db node)
    app_nodes = [n for n in nodes if n.get("category") == "APPLICATION"]
    db_nodes = [n for n in nodes if n.get("category") == "DATABASE"]
    az_patterns = [n for n in nodes if "AZ-" in n.get("name", "") or "AZ-" in n.get("nodeId", "")
                   or "Standby" in n.get("name", "") or "Replica" in n.get("name", "")]
    has_multi_az = len(app_nodes) >= 2 or len(db_nodes) >= 2 or len(az_patterns) >= 2
    report.add("HA_REQUIREMENT_SATISFIED",
        QualityResult.PASS if not ("HIGH_AVAILABILITY" in req.availability) or has_multi_az else QualityResult.FAIL,
        f"HA requested: {'HIGH_AVAILABILITY' in req.availability}, multi-AZ: {has_multi_az}")

    # Container check
    container_requested = "KUBERNETES" in req.platform
    container_nodes = [n for n in nodes if n.get("platform") in ("KUBERNETES", "OPENSHIFT_OCP")]
    report.add("CONTAINER_REQUIREMENT_SATISFIED",
        QualityResult.PASS if not container_requested or len(container_nodes) > 0 else QualityResult.FAIL,
        f"Container: {len(container_nodes)} nodes")

    # Security boundaries
    has_waf = any("waf" in n.get("nativeService", "").lower() for n in nodes)
    has_kms = any("kms" in n.get("nativeService", "").lower() for n in nodes)
    has_secrets = any("secret" in n.get("nativeService", "").lower() or "vault" in n.get("nativeService", "").lower() for n in nodes)
    report.add("SECURITY_BOUNDARIES",
        QualityResult.WARN if not (has_waf and has_kms and has_secrets) else QualityResult.PASS,
        f"WAF:{has_waf} KMS:{has_kms} Secrets:{has_secrets}")

    # Monitoring not in request path
    obs_nodes = [n for n in nodes if n.get("category") == "OBSERVABILITY"]
    obs_in_path = [
        e for e in edges
        if any(n.get("nodeId") == e.get("sourceNodeId") and n.get("category") == "OBSERVABILITY" for n in nodes)
        and e.get("type") not in ("telemetry",)
    ]
    report.add("NO_MONITORING_IN_REQUEST_PATH",
        QualityResult.FAIL if obs_in_path else QualityResult.PASS,
        f"Monitoring in path: {obs_in_path}" if obs_in_path else "Monitoring is cross-cutting")

    # KMS not in request path
    kms_nodes = [n for n in nodes if "kms" in n.get("nativeService", "").lower()]
    kms_in_path = [
        e for e in edges
        if any(n.get("nodeId") == e.get("sourceNodeId") and "kms" in n.get("nativeService", "").lower() for n in nodes)
        and e.get("type") not in ("key_usage", "control")
    ]
    report.add("NO_KMS_IN_REQUEST_PATH",
        QualityResult.FAIL if kms_in_path else QualityResult.PASS,
        f"KMS in request path" if kms_in_path else "KMS as supporting service")

    # No orphan nodes
    referenced = set()
    for e in edges:
        referenced.add(e.get("sourceNodeId", ""))
        referenced.add(e.get("targetNodeId", ""))
    orphans = [n.get("nodeId") for n in nodes if n.get("nodeId") not in referenced]
    report.add("NO_ORPHAN_NODES",
        QualityResult.FAIL if orphans else QualityResult.PASS,
        f"Orphaned: {orphans}" if orphans else "All nodes connected")

    # Observability present
    has_obs = len(obs_nodes) > 0
    report.add("OBSERVABILITY_PRESENT",
        QualityResult.PASS if has_obs else QualityResult.WARN,
        "Monitoring service present" if has_obs else "No monitoring service")

    # Data flow valid (at least one DATA edge)
    data_edges = [e for e in edges if e.get("type") == "data"]
    report.add("DATA_FLOW_VALID",
        QualityResult.PASS if data_edges else QualityResult.WARN,
        f"{len(data_edges)} data edges")

    # Encryption present
    tls_edges = [e for e in edges if "TLS" in e.get("protocol", "").upper() or "HTTPS" in e.get("protocol", "").upper()]
    report.add("ENCRYPTION_CONTROL_PRESENT",
        QualityResult.PASS if has_kms and tls_edges else QualityResult.WARN,
        f"KMS:{has_kms} TLS edges:{len(tls_edges)}")

    return report


def _make_node(
    node_id: str, name: str, category: str, provider: str,
    native_service: str, platform: str = "NATIVE_VM",
    security_zone: str = "private", data_classification: str = "internal",
    owner: str = "", source: str = "AI_GENERATED",
) -> GeneratedNode:
    sv = validate_service(provider, native_service)
    # Use provider-native display name
    display = get_display_name(provider, native_service) if native_service else name
    return GeneratedNode(
        node_id=node_id,
        name=display if native_service else name,  # Provider-native label
        category=category,
        provider=provider, native_service=native_service, platform=platform,
        security_zone=security_zone, data_classification=data_classification,
        owner=owner, source=source,
        service_verification=sv.value,
    )


def select_pattern(req: DetectedRequirement, is_ha: bool, has_pdpa: bool) -> ArchitecturePattern:
    """Select architecture pattern from requirements."""
    if is_ha and req.provider in ("AWS", "GCP"):
        return ArchitecturePattern.INTERNET_FACING_MULTI_AZ_WEB_APPLICATION
    if req.platform in ("KUBERNETES", "OPENSHIFT_OCP"):
        return ArchitecturePattern.MICROSERVICES
    return ArchitecturePattern.THREE_TIER_APPLICATION


def generate_architecture(request: AgainPilotRequest) -> AgainPilotProposal:
    """Generate architecturally coherent, provider-native topology.

    Phase Q: Architecture Quality — pattern → topology → services → flows → layout.
    """
    req = extract_requirements(request.brief)
    provider = request.provider_preference.value if request.provider_preference != ProviderPreference.AUTO else req.provider
    platform = request.platform_preference.value if request.platform_preference != PlatformPreference.AUTO else req.platform

    is_aws = provider == "AWS"
    is_gcp = provider == "GCP"
    is_ha = "HIGH_AVAILABILITY" in req.availability
    is_private_db = "PRIVATE_DATABASE" in req.security
    has_pdpa = "PDPA" in req.compliance
    is_container = platform in ("KUBERNETES", "OPENSHIFT_OCP")
    is_detailed = request.generation_depth == GenerationDepth.DETAILED

    pattern = select_pattern(req, is_ha, has_pdpa)

    nodes: list[GeneratedNode] = []
    edges: list[GeneratedEdge] = []
    recs: list[dict] = []

    # ═══════════════════════════════════════════════════
    # TOPOLOGY — Semantic boundary groups
    # ═══════════════════════════════════════════════════

    groups = [
        GeneratedGroup("GRP-INTERNET", "Internet", TopologyZone.EXTERNAL_SYSTEM.value, "", provider, "public", []),
        GeneratedGroup("GRP-CLOUD", f"{provider} Cloud", TopologyZone.CLOUD_BOUNDARY.value, "", provider, "public", []),
    ]

    if is_aws or is_gcp:
        groups.append(GeneratedGroup("GRP-VPC", "VPC", TopologyZone.NETWORK_BOUNDARY.value, "GRP-CLOUD", provider, "private", []))
        groups.append(GeneratedGroup("GRP-EDGE", "Edge Services", TopologyZone.SECURITY_ZONE.value, "GRP-VPC", provider, "dmz", []))
        groups.append(GeneratedGroup("GRP-PUBLIC", "Public Subnets", TopologyZone.SUBNET_GROUP.value, "GRP-VPC", provider, "dmz", []))
        groups.append(GeneratedGroup("GRP-APP", "Private Application Subnets", TopologyZone.SUBNET_GROUP.value, "GRP-VPC", provider, "private", []))
        groups.append(GeneratedGroup("GRP-DATA", "Private Data Subnets", TopologyZone.SUBNET_GROUP.value, "GRP-VPC", provider, "private", []))
        groups.append(GeneratedGroup("GRP-SECURITY", "Security Services", TopologyZone.SECURITY_ZONE.value, "GRP-CLOUD", provider, "private", []))
        groups.append(GeneratedGroup("GRP-OBS", "Observability", TopologyZone.SECURITY_ZONE.value, "GRP-CLOUD", provider, "private", []))

    # ═══════════════════════════════════════════════════
    # TIER 0 — External User
    # ═══════════════════════════════════════════════════

    user_nid = "NODE-USER-001"
    nodes.append(_make_node(user_nid, "End User", "USER", "EXTERNAL", "", "WEB", "public", "none"))

    # ═══════════════════════════════════════════════════
    # TIER 1 — Edge / Ingress
    # ═══════════════════════════════════════════════════

    dns_svc = "route53" if is_aws else "cloud_dns" if is_gcp else "bind"
    cdn_svc = "cloudfront" if is_aws else "cloud_cdn" if is_gcp else ""
    waf_svc = "waf" if is_aws else "cloud_armor" if is_gcp else "nginx"
    lb_svc = "alb" if is_aws else "cloud_lb" if is_gcp else "haproxy"

    dns_nid = "NODE-DNS-001"
    cdn_nid = "NODE-CDN-001"
    waf_nid = "NODE-WAF-001"
    lb_nid = "NODE-LB-001"

    nodes.append(_make_node(dns_nid, "DNS", "DNS", provider, dns_svc, "NATIVE_VM", "public", "none"))
    if cdn_svc:
        nodes.append(_make_node(cdn_nid, "CDN", "NETWORK", provider, cdn_svc, "NATIVE_VM", "public", "none"))
    nodes.append(_make_node(waf_nid, "Web Firewall", "SECURITY", provider, waf_svc, "NATIVE_VM", "dmz", "none"))
    nodes.append(_make_node(lb_nid, "Load Balancer", "NETWORK", provider, lb_svc, "NATIVE_VM", "dmz", "none"))

    # ═══════════════════════════════════════════════════
    # TIER 2 — Application (containerized, HA)
    # ═══════════════════════════════════════════════════

    app_svc = "ecs" if is_aws else "cloud_run" if is_gcp else "kubernetes"
    app_nid_a = "NODE-APP-001"
    nodes.append(_make_node(app_nid_a, "Application", "APPLICATION", provider, app_svc, platform, "private", "internal", "platform-team"))
    if is_ha:
        app_nid_b = "NODE-APP-002"
        nodes.append(_make_node(app_nid_b, "Application (AZ-B)", "APPLICATION", provider, app_svc, platform, "private", "internal", "platform-team"))

    # ═══════════════════════════════════════════════════
    # TIER 3 — Data (private, HA)
    # ═══════════════════════════════════════════════════

    db_svc = "rds" if is_aws else "cloud_sql" if is_gcp else "postgresql"
    db_nid = "NODE-DB-001"
    data_class = "pii" if has_pdpa else "internal"
    nodes.append(_make_node(db_nid, "Database", "DATABASE", provider, db_svc, "NATIVE_VM", "private", data_class, "data-team"))
    if is_ha:
        nodes.append(_make_node("NODE-DB-002", "Database Standby", "DATABASE", provider, db_svc, "NATIVE_VM", "private", data_class, "data-team"))

    # Storage
    store_svc = "s3" if is_aws else "cloud_storage" if is_gcp else "minio"
    store_nid = "NODE-STORE-001"
    nodes.append(_make_node(store_nid, "Object Storage", "STORAGE", provider, store_svc, "NATIVE_VM", "private", "internal"))

    # Cache (for HA/detailed)
    if is_ha or is_detailed:
        cache_svc = "elasticache" if is_aws else "memorystore" if is_gcp else "redis"
        cache_nid = "NODE-CACHE-001"
        nodes.append(_make_node(cache_nid, "Cache", "CACHE", provider, cache_svc, "NATIVE_VM", "private", "internal"))

    # ═══════════════════════════════════════════════════
    # TIER S — Supporting: Security + Observability
    # ═══════════════════════════════════════════════════

    kms_svc = "kms"
    secret_svc = "secrets_manager" if is_aws else "secret_manager" if is_gcp else "vault"
    obs_svc = "cloudwatch" if is_aws else "cloud_monitoring" if is_gcp else "prometheus"

    kms_nid = "NODE-KMS-001"
    secret_nid = "NODE-SECRET-001"
    obs_nid = "NODE-OBS-001"

    nodes.append(_make_node(kms_nid, "Key Management", "SECURITY", provider, kms_svc, "NATIVE_VM", "private", "internal", "security-team"))
    nodes.append(_make_node(secret_nid, "Secrets Manager", "SECURITY", provider, secret_svc, "NATIVE_VM", "private", "internal", "security-team"))
    nodes.append(_make_node(obs_nid, "Monitoring", "OBSERVABILITY", provider, obs_svc, "NATIVE_VM", "private", "internal", "platform-team"))

    # Identity (for PDPA)
    auth_nid = ""
    if has_pdpa:
        auth_svc = "cognito" if is_aws else "keycloak"
        auth_nid = "NODE-AUTH-001"
        nodes.append(_make_node(auth_nid, "Identity Provider", "IDENTITY", provider, auth_svc, "NATIVE_VM", "private", "pii", "security-team"))

    # ═══════════════════════════════════════════════════
    # EDGES — Semantic flow types
    # ═══════════════════════════════════════════════════

    edge_idx = 0
    def add_edge(src: str, tgt: str, etype: str = EdgeType.REQUEST.value,
                 proto: str = "HTTPS", direction: str = "unidirectional",
                 dtype: str = "", sec: str = "none", lbl: str = ""):
        nonlocal edge_idx
        edge_idx += 1
        edges.append(GeneratedEdge(f"EDGE-{edge_idx:03d}", src, tgt, etype, proto, direction, dtype, sec, lbl or proto))

    # Request path: User → DNS → CDN → WAF → ALB → App
    add_edge(user_nid, dns_nid, EdgeType.REQUEST.value, "DNS", lbl="DNS")
    if cdn_svc:
        add_edge(dns_nid, cdn_nid, EdgeType.REQUEST.value, "HTTPS", lbl="HTTPS")
        add_edge(cdn_nid, waf_nid, EdgeType.REQUEST.value, "HTTPS", lbl="HTTPS")
    else:
        add_edge(dns_nid, waf_nid, EdgeType.REQUEST.value, "HTTPS", lbl="HTTPS")
    add_edge(waf_nid, lb_nid, EdgeType.REQUEST.value, "HTTPS", lbl="HTTPS")
    add_edge(lb_nid, app_nid_a, EdgeType.REQUEST.value, "HTTP", lbl="HTTP")
    if is_ha:
        add_edge(lb_nid, app_nid_b, EdgeType.REQUEST.value, "HTTP", lbl="HTTP")

    # Data path: App → DB (SQL, private), App → Storage, App → Cache
    add_edge(app_nid_a, db_nid, EdgeType.DATA.value, "TCP", "bidirectional", "SQL", "pii", "SQL/TLS")
    if is_ha:
        add_edge(db_nid, "NODE-DB-002", EdgeType.DATA.value, "TCP", "bidirectional", "SQL", "pii", "Replication")
    add_edge(app_nid_a, store_nid, EdgeType.DATA.value, "HTTPS", "bidirectional", "blob", "internal", "S3 API")
    if is_ha or is_detailed:
        add_edge(app_nid_a, cache_nid, EdgeType.DATA.value, "TCP", "bidirectional", "cache", "internal", "Cache")

    # Auth: Identity → App (if PDPA)
    if auth_nid:
        add_edge(auth_nid, app_nid_a, EdgeType.AUTH.value, "HTTPS", lbl="Auth")

    # Supporting edges (NOT in request path)
    add_edge(app_nid_a, secret_nid, EdgeType.SECRET_ACCESS.value, "HTTPS", lbl="Secrets")
    add_edge(app_nid_a, kms_nid, EdgeType.KEY_USAGE.value, "HTTPS", lbl="Key Usage")
    if db_nid:
        add_edge(db_nid, kms_nid, EdgeType.KEY_USAGE.value, "HTTPS", lbl="Encrypt")
    add_edge(app_nid_a, obs_nid, EdgeType.TELEMETRY.value, "HTTPS", lbl="Metrics")
    add_edge(lb_nid, obs_nid, EdgeType.TELEMETRY.value, "HTTPS", lbl="ALB Metrics")
    add_edge(db_nid, obs_nid, EdgeType.TELEMETRY.value, "HTTPS", lbl="DB Metrics")

    # ═══════════════════════════════════════════════════
    # RECOMMENDATIONS — Deduplicated
    # ═══════════════════════════════════════════════════

    seen_svcs: set[str] = set()
    for n in nodes:
        if n.native_service and n.native_service not in seen_svcs:
            seen_svcs.add(n.native_service)
            catalog = get_provider_catalog(provider)
            sv_key = n.native_service.lower().replace(" ", "_")
            desc = catalog.get(sv_key, {}).get("description", "")
            display = get_display_name(provider, n.native_service)
            recs.append({
                "nodeId": n.node_id,
                "service": n.native_service,
                "displayName": display,
                "category": n.category,
                "description": desc,
                "verification": n.service_verification,
                "rationale": f"Provider-native {n.category} service: {display}",
            })

    # ═══════════════════════════════════════════════════
    # META — Assumptions, Risks, Questions
    # ═══════════════════════════════════════════════════

    assumptions = [
        f"Provider: {provider}", f"Pattern: {pattern.value}",
        f"Platform: {platform} deployment",
        "Private database access — no public route" if is_private_db else "Database access via application tier",
        f"High availability: {'Multi-AZ deployment' if is_ha else 'Single-AZ'}",
        f"{'PDPA privacy considerations applied' if has_pdpa else 'Standard security'}",
        "HTTPS/TLS for all external traffic",
        "VPC with public/private subnet separation",
        "Supporting services (KMS, Secrets, Monitoring) outside request path",
    ]

    risks = [
        "Service selection from deterministic catalog — verify against actual requirements",
        f"Load estimate ({req.expected_load}) from brief — refine with actual data",
    ]
    if is_ha:
        risks.append("Multi-AZ increases cost — validate budget")
    if has_pdpa:
        risks.append("PDPA requires formal DPIA beyond architecture design")
        risks.append("Data residency may restrict region selection")

    questions = [
        "Which AWS region is preferred for data residency?",
        "What is the monthly infrastructure budget?",
        "Existing CI/CD tooling to integrate (GitHub Actions, Jenkins)?",
        "Preferred authentication: Cognito, external SAML/OIDC IdP?",
        "What RTO/RPO targets for disaster recovery?",
    ]

    # ═══════════════════════════════════════════════════
    # VIEWS — Distinct semantic views
    # ═══════════════════════════════════════════════════

    all_nids = [n.node_id for n in nodes]
    all_eids = [e.edge_id for e in edges]

    # Data Flow: data + storage nodes, data edges only
    data_nids = [n.node_id for n in nodes if n.category in ("DATABASE", "STORAGE", "CACHE")]
    data_eids = [e.edge_id for e in edges if e.edge_type == EdgeType.DATA.value]

    # Operation Flow: request-path nodes + request edges
    ops_nids = [n.node_id for n in nodes if n.category in ("USER", "DNS", "NETWORK", "APPLICATION")]
    ops_eids = [e.edge_id for e in edges if e.edge_type == EdgeType.REQUEST.value]

    # Security Flow: security/identity nodes + auth/secret/key edges
    sec_nids = [n.node_id for n in nodes if n.category in ("SECURITY", "IDENTITY")]
    sec_eids = [e.edge_id for e in edges if e.edge_type in (
        EdgeType.AUTH.value, EdgeType.SECRET_ACCESS.value, EdgeType.KEY_USAGE.value,
    )]

    views = {
        "architecture": {"nodes": all_nids, "edges": all_eids},
        "dataFlow": {"nodes": data_nids, "edges": data_eids},
        "operationFlow": {"nodes": ops_nids, "edges": ops_eids},
        "securityFlow": {"nodes": sec_nids, "edges": sec_eids},
    }

    # ═══════════════════════════════════════════════════
    # QUALITY — Validate before returning
    # ═══════════════════════════════════════════════════

    node_dicts = [n.to_dict() for n in nodes]
    edge_dicts = [e.to_dict() for e in edges]
    group_dicts = [g.to_dict() for g in groups]
    quality = validate_architecture_quality(node_dicts, edge_dicts, group_dicts, provider, req, pattern.value)

    # If quality fails, attempt one correction pass
    if quality.overall == QualityResult.FAIL:
        # Strip duplicate recommendations
        recs = list({r["service"]: r for r in recs}.values())
        # Re-check
        quality = validate_architecture_quality(node_dicts, edge_dicts, group_dicts, provider, req, pattern.value)

    # Derive title from pattern + provider
    title_parts = ["Architecture"]
    if "patient" in request.brief.lower() or "portal" in request.brief.lower():
        title_parts = ["Patient Portal Architecture"]
    title = f"{' '.join(title_parts)} — {provider} ({pattern.value})"

    brief_hash = hashlib.sha256(request.brief.encode()).hexdigest()[:12]

    return AgainPilotProposal(
        title=title,
        summary=f"{provider} {pattern.value}. {len(nodes)} services, {len(edges)} connections. "
                f"{'HA ' if is_ha else ''}{'PDPA ' if has_pdpa else ''}design. "
                f"Quality: {quality.overall.value}.",
        detected_requirements=req,
        nodes=nodes, edges=edges, groups=groups,
        views=views,
        native_service_recommendations=recs,
        assumptions=assumptions, risks=risks, clarifying_questions=questions,
        rationale=f"Architecture Pattern: {pattern.value}\nProvider: {provider}\nPlatform: {platform}\n"
                  f"Load: {req.expected_load}\nHA: {is_ha}\nPrivate DB: {is_private_db}\n"
                  f"Compliance: {', '.join(req.compliance) if req.compliance else 'Standard'}",
        generation_provider="DETERMINISTIC_FALLBACK",
        generation_model="againpilot-q2",
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


# ═══════════════════════════════════════════════════════════════════
# REAL AI PROVIDER — Two-Stage Ollama Integration
# ═══════════════════════════════════════════════════════════════════

import os as _os
import urllib.request as _ur

OLLAMA_BASE = _os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _os.environ.get("AGAINPILOT_OLLAMA_MODEL", "qwen2.5:7b")
STAGE1_TIMEOUT = int(_os.environ.get("AGAINPILOT_STAGE1_TIMEOUT", "60"))
STAGE2_TIMEOUT = int(_os.environ.get("AGAINPILOT_STAGE2_TIMEOUT", "90"))


def _ollama_available() -> bool:
    try:
        req = _ur.Request(f"{OLLAMA_BASE}/api/tags", method="GET")
        with _ur.urlopen(req, timeout=5) as r:
            models = [m["name"] for m in json.loads(r.read()).get("models", [])]
            return any(OLLAMA_MODEL.split(":")[0] in m for m in models)
    except Exception:
        return False


def _ollama_chat(system_prompt: str, user_message: str, max_tokens: int = 2048, timeout: int = 60) -> str:
    payload = json.dumps({
        "model": OLLAMA_MODEL, "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "options": {"temperature": 0.3, "num_predict": max_tokens},
    }).encode("utf-8")
    req = _ur.Request(f"{OLLAMA_BASE}/api/chat", data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    with _ur.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()).get("message", {}).get("content", "")


def _parse_json(text: str) -> dict | None:
    t = text.strip()
    if t.startswith("```"):  # strip markdown fences
        lines = t.split("\n")
        if lines[0].startswith("```"): lines = lines[1:]
        if lines and lines[-1].strip() == "```": lines = lines[:-1]
        t = "\n".join(lines)
    s, e = t.find("{"), t.rfind("}")
    if s >= 0 and e > s:
        try: return json.loads(t[s:e+1])
        except json.JSONDecodeError: pass
    return None


# ── Compact Stage 1: ArchitectureIntent ──

ARCHITECTURE_INTENT_PROMPT = """You are a cloud architect. From a brief, produce a compact ArchitectureIntent JSON.

RULES:
- Detect system type, provider, platform, load, requirements
- List ONLY the provider-native services that are NEEDED
- Be concise: target < 2KB output
- Return ONLY valid JSON, no markdown fences, no explanation

{
  "systemType": "patient_portal|web_app|data_platform|microservices|enterprise_app",
  "provider": "AWS|GCP|ON_PREM",
  "platform": "NATIVE_VM|KUBERNETES|BARE_METAL",
  "loadProfile": "10000 users/day",
  "availability": ["HIGH_AVAILABILITY"],
  "security": ["PRIVATE_DATABASE","ENCRYPTION_REQUIRED"],
  "compliance": ["PDPA"],
  "dataClassification": ["PERSONAL_DATA"],
  "components": ["route53","cloudfront","waf","alb","ecs","rds","s3","elasticache","kms","secrets_manager","cloudwatch","cognito"],
  "architecturePattern": "INTERNET_FACING_MULTI_AZ_WEB_APPLICATION",
  "assumptions": ["containerized workload","private database"],
  "questions": ["preferred AWS region?"]
}"""


# ── Compact Stage 2: ArchitectureProposal from Intent ──

ARCHITECTURE_PROPOSAL_PROMPT = """From ArchitectureIntent + filtered service catalog, produce ArchitectureProposal JSON.

MANDATORY ROLES — you MUST include at minimum these semantic roles:
- dns (route53/cloud_dns): DNS resolution
- cdn (cloudfront/cloud_cdn): CDN/caching at edge
- waf: web application firewall
- lb (alb/cloud_lb): load balancer
- app (ecs/cloud_run/kubernetes): application runtime (with ha=true for multi-AZ)
- db (rds/cloud_sql/postgresql): database (with ha=true for multi-AZ, zone=private-data)
- storage (s3/cloud_storage/minio): object storage
- cache (elasticache/memorystore/redis): cache layer
- kms: key management for encryption
- secrets (secrets_manager/secret_manager/vault): secrets storage
- observability (cloudwatch/cloud_monitoring/prometheus): monitoring
- identity (cognito/keycloak): required if PDPA/compliance requested

RULES:
- Use ONLY services from the provided catalog
- Private DB: no public route to database (zone=private-data)
- HA: set ha=true on app and db nodes (backend creates AZ pairs)
- Security services (kms, secrets) are SUPPORTING — NOT in request path
- Observability is TELEMETRY — NOT in request path
- Use semantic edge types: request, data, auth, secret_access, key_usage, telemetry
- Return ONLY valid JSON, no markdown

COMPACT NODE: {"id":"app","role":"APPLICATION","svc":"ecs","zone":"private-app","ha":true}
COMPACT EDGE: {"from":"user","to":"dns","type":"request","proto":"DNS","label":"DNS"}
GROUP: {"id":"vpc","name":"VPC","type":"NETWORK_BOUNDARY","zone":"private"}

Backend expands these into full canonical model. Do NOT generate positions, colors, layout coordinates.
Include ALL mandatory roles. Return JSON with nodes, edges, groups, assumptions, risks, questions, rationale."""


# ── Service catalog filter ──

def _filter_catalog(provider: str, intent_components: list[str]) -> str:
    """Return only relevant services from catalog."""
    catalog = get_provider_catalog(provider)
    filtered = {}
    for comp in intent_components:
        key = comp.lower().replace(" ", "_").replace("-", "_")
        if key in catalog:
            filtered[key] = catalog[key]
    # Always include essentials
    for essential in ["kms", "secrets_manager", "cloudwatch"]:
        ek = essential if provider == "AWS" else ("secret_manager" if essential == "secrets_manager" else "cloud_monitoring" if essential == "cloudwatch" else essential)
        if ek not in filtered:
            for k, v in catalog.items():
                if k == ek or (essential == "kms" and "kms" in k):
                    filtered[k] = v; break
    return "\n".join([f"{k}: {v['category']} — {v['description']}" for k, v in filtered.items()])


# ── Build full proposal from LLM compact output ──

def _build_proposal_from_compact(
    compact: dict, req: DetectedRequirement, provider: str, model: str,
    stage1_ms: int, stage2_ms: int,
) -> AgainPilotProposal | None:
    """Expand compact LLM output into full ArchitectureProposal."""
    try:
        nodes: list[GeneratedNode] = []
        edges: list[GeneratedEdge] = []
        groups: list[GeneratedGroup] = []
        node_map: dict[str, str] = {}
        nid_counter = 0

        def next_nid(prefix: str = "NODE") -> str:
            nonlocal nid_counter; nid_counter += 1
            return f"{prefix}-{nid_counter:03d}"

        # Groups from LLM
        for g in compact.get("groups", []):
            groups.append(GeneratedGroup(g.get("id", next_nid("GRP")), g.get("name", ""),
                g.get("type", "SUBNET_GROUP"), g.get("parent", ""), provider,
                g.get("zone", "private")))

        # Nodes from LLM compact format
        for cn in compact.get("nodes", []):
            nid = cn.get("id", next_nid("NODE"))
            svc = cn.get("svc", "")
            role = cn.get("role", "APPLICATION")
            zone = cn.get("zone", "private")
            is_ha = cn.get("ha", False)
            name = get_display_name(provider, svc) if svc else cn.get("name", role)
            node_map[nid] = nid
            nodes.append(GeneratedNode(nid, name, role, provider, svc,
                "KUBERNETES" if "KUBERNETES" in req.platform else "NATIVE_VM",
                zone, "pii" if zone == "private-data" else "internal",
                "", "AI_GENERATED", "UNVERIFIED",
                service_verification=validate_service(provider, svc).value))
            if is_ha:
                nid2 = nid + "-b"
                node_map[nid2] = nid2
                nodes.append(GeneratedNode(nid2, name + " (AZ-B)", role, provider, svc,
                    "KUBERNETES" if "KUBERNETES" in req.platform else "NATIVE_VM",
                    zone, "pii" if zone == "private-data" else "internal",
                    "", "AI_GENERATED", "UNVERIFIED",
                    service_verification=validate_service(provider, svc).value))

        # Edges from LLM compact format
        eid_counter = 0
        for ce in compact.get("edges", []):
            eid_counter += 1
            edges.append(GeneratedEdge(f"EDGE-{eid_counter:03d}",
                ce.get("from", ""), ce.get("to", ""),
                ce.get("type", "request"), ce.get("proto", "TCP"),
                ce.get("dir", "unidirectional"), ce.get("dataType", ""),
                ce.get("sec", "none"), ce.get("label", ce.get("proto", ""))))

        # Build views from edge types
        all_nids = [n.node_id for n in nodes]
        all_eids = [e.edge_id for e in edges]
        data_nids = [n.node_id for n in nodes if n.category in ("DATABASE", "STORAGE", "CACHE")]
        data_eids = [e.edge_id for e in edges if e.edge_type == "data"]
        ops_nids = [n.node_id for n in nodes if n.category in ("USER", "DNS", "NETWORK", "APPLICATION")]
        ops_eids = [e.edge_id for e in edges if e.edge_type == "request"]
        sec_nids = [n.node_id for n in nodes if n.category in ("SECURITY", "IDENTITY")]
        sec_eids = [e.edge_id for e in edges if e.edge_type in ("auth", "secret_access", "key_usage")]

        return AgainPilotProposal(
            title=compact.get("title", f"{provider} Architecture"),
            summary=compact.get("summary", ""), detected_requirements=req,
            nodes=nodes, edges=edges, groups=groups,
            views={"architecture": {"nodes": all_nids, "edges": all_eids},
                   "dataFlow": {"nodes": data_nids, "edges": data_eids},
                   "operationFlow": {"nodes": ops_nids, "edges": ops_eids},
                   "securityFlow": {"nodes": sec_nids, "edges": sec_eids}},
            native_service_recommendations=[],
            assumptions=compact.get("assumptions", []),
            risks=compact.get("risks", []),
            clarifying_questions=compact.get("questions", []),
            rationale=compact.get("rationale", ""),
            generation_provider="LOCAL_LLM", generation_model=model,
            brief_hash=hashlib.sha256(str(stage1_ms).encode()).hexdigest()[:12],
        )
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# REAL AI GENERATION — Two-Stage Pipeline
# ═══════════════════════════════════════════════════════════════════

def _generate_real_ai(
    brief: str, provider_pref: str, platform_pref: str,
    req: DetectedRequirement, provider: str,
) -> tuple[AgainPilotProposal | None, dict]:
    """Two-stage real AI generation. Returns (proposal, provenance_dict)."""
    prov = {"mode": "REAL_LLM", "provider": "LOCAL_LLM", "model": OLLAMA_MODEL,
            "stage1Ms": 0, "stage2Ms": 0, "result": "FAILED"}

    if not _ollama_available():
        prov["result"] = "FALLBACK_LLM_UNAVAILABLE"
        return None, prov

    # ═══ STAGE 1: ArchitectureIntent ═══
    import time
    t0 = time.time()
    try:
        intent_raw = _ollama_chat(ARCHITECTURE_INTENT_PROMPT,
            f"Architecture Brief:\n{brief}\n\nProvider: {provider_pref}\nPlatform: {platform_pref}",
            max_tokens=1024, timeout=STAGE1_TIMEOUT)
    except Exception:
        prov["result"] = "STAGE1_TIMEOUT"
        return None, prov

    prov["stage1Ms"] = int((time.time() - t0) * 1000)
    intent = _parse_json(intent_raw)

    if not intent:
        prov["result"] = "STAGE1_INVALID_JSON"
        return None, prov

    # ═══ Filter catalog ═══
    components = intent.get("components", [])
    filtered = _filter_catalog(provider, components)
    full_catalog = get_provider_catalog(provider)

    # ═══ STAGE 2: ArchitectureProposal ═══
    t1 = time.time()
    try:
        prop_raw = _ollama_chat(ARCHITECTURE_PROPOSAL_PROMPT,
            f"Architecture Intent: {json.dumps(intent)}\n\nFiltered Service Catalog ({provider}):\n{filtered}",
            max_tokens=2048, timeout=STAGE2_TIMEOUT)
    except Exception:
        prov["result"] = "STAGE2_TIMEOUT"
        return None, prov

    prov["stage2Ms"] = int((time.time() - t1) * 1000)
    compact = _parse_json(prop_raw)

    if not compact:
        prov["result"] = "STAGE2_INVALID_JSON"
        return None, prov

    proposal = _build_proposal_from_compact(compact, req, provider, OLLAMA_MODEL, prov["stage1Ms"], prov["stage2Ms"])
    if not proposal:
        prov["result"] = "BUILD_FAILED"
        return None, prov

    # Quality validation
    node_dicts = [n.to_dict() for n in proposal.nodes]
    edge_dicts = [e.to_dict() for e in proposal.edges]
    group_dicts = [g.to_dict() for g in proposal.groups]
    quality = validate_architecture_quality(node_dicts, edge_dicts, group_dicts, provider, req, "LLM_TWO_STAGE")
    if quality.overall == QualityResult.FAIL:
        prov["result"] = "QUALITY_FAIL"
        # One correction attempt
        try:
            fail_msg = "\n".join([f"- {c['gate']}: {c['detail']}" for c in quality.checks if c['result'] == 'FAIL'])
            correction = _ollama_chat(
                ARCHITECTURE_PROPOSAL_PROMPT + f"\n\nFix quality failures:\n{fail_msg}\nReturn corrected JSON.",
                f"Previous output: {json.dumps(compact)}\nFix quality issues.",
                2048, STAGE2_TIMEOUT,
            )
            compact2 = _parse_json(correction)
            if compact2:
                proposal2 = _build_proposal_from_compact(compact2, req, provider, OLLAMA_MODEL, prov["stage1Ms"], prov["stage2Ms"])
                if proposal2:
                    prov["result"] = "REAL_LLM_CORRECTED"
                    return proposal2, prov
        except Exception:
            pass
        return None, prov

    prov["result"] = "REAL_LLM"
    return proposal, prov


# ═══════════════════════════════════════════════════════════════════
# AGAINPILOT PROVIDER ROUTER
# ═══════════════════════════════════════════════════════════════════

class AgainPilotProviderRouter:
    def __init__(self):
        self._ollama = _ollama_available()
        self._mode = AIGenerationMode.REAL_LLM if self._ollama else AIGenerationMode.DETERMINISTIC_FALLBACK
        self._provider = AIProvider.LOCAL_LLM if self._ollama else AIProvider.NONE
        self._last_result_mode = ""
        self._last_provenance: dict = {}

    @property
    def mode(self) -> AIGenerationMode: return self._mode

    @property
    def provider_name(self) -> str: return self._provider.value

    @property
    def model_name(self) -> str: return OLLAMA_MODEL if self._ollama else "againpilot-q2"

    @property
    def last_result_mode(self) -> str: return self._last_result_mode

    @property
    def last_provenance(self) -> dict: return dict(self._last_provenance)

    def generate(self, request: AgainPilotRequest) -> AgainPilotProposal:
        req = extract_requirements(request.brief)
        provider = request.provider_preference.value if request.provider_preference != ProviderPreference.AUTO else req.provider
        self._last_result_mode = ""
        self._last_provenance = {}

        # Try REAL LLM
        if self._ollama:
            proposal, prov = _generate_real_ai(
                request.brief, request.provider_preference.value,
                request.platform_preference.value, req, provider)
            self._last_provenance = prov
            if proposal:
                self._last_result_mode = prov["result"]
                return proposal

        # DETERMINISTIC FALLBACK — only if explicitly allowed or LLM unavailable
        self._last_result_mode = "DETERMINISTIC_FALLBACK"
        self._last_provenance = {"mode": "DETERMINISTIC_FALLBACK", "result": "FALLBACK"}
        return generate_architecture(request)

    def refine(self, nodes: list[dict], edges: list[dict], instruction: str, provider: str = "AWS") -> tuple[AgainPilotProposal, RefineDelta]:
        return refine_architecture(nodes, edges, instruction, provider)

    def explain(self, nodes: list[dict], edges: list[dict], provider: str) -> str:
        if self._ollama:
            try:
                node_text = "\n".join([f"- {n.get('name','?')} ({n.get('category','?')}) [{n.get('nativeService','')}]" for n in nodes[:20]])
                edge_text = "\n".join([f"- {e.get('sourceNodeId','?')} → {e.get('targetNodeId','?')} [{e.get('type','?')}: {e.get('label','')}]" for e in edges[:20]])
                resp = _ollama_chat("Explain this cloud architecture concisely. Services, layout, security, availability. No chain-of-thought.",
                    f"Provider: {provider}\nNodes:\n{node_text}\n\nEdges:\n{edge_text}", 1024, 30)
                if resp: return resp
            except Exception: pass
        return explain_architecture(nodes, edges, provider)

    def analyze_security(self, nodes: list[dict], edges: list[dict], req: DetectedRequirement) -> SecurityAnalysis:
        return analyze_security(nodes, edges, req)


_againpilot = AgainPilotProviderRouter()

def get_againpilot() -> AgainPilotProviderRouter:
    return _againpilot
