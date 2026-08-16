"""
Conductor Again — Complexity Analyzer
Scores functions by multiple dimensions: structural, domain, integration, data, uncertainty.
"""

from dataclasses import dataclass, field


@dataclass
class ComplexityBreakdown:
    structural: float = 0.0     # Logic depth, branching, states
    domain: float = 0.0         # Domain knowledge required
    integration: float = 0.0    # External dependencies, APIs
    data: float = 0.0           # Data volume, schema complexity
    uncertainty: float = 0.0    # Ambiguity, unclear requirements
    overall: float = 0.0


COMPLEXITY_KEYWORDS = {
    "structural": [
        "state machine", "workflow", "approval", "multi-step", "conditional",
        "branching", "concurrent", "parallel", "queue", "scheduler", "batch",
        "transaction", "rollback", "retry", "timeout", "deadline",
    ],
    "domain": [
        "regulatory", "compliance", "tax", "accounting", "legal", "audit",
        "medical", "financial", "certification", "sox", "gdpr", "hipaa",
        "bom", "routing", "formula", "yield", "recipe",
    ],
    "integration": [
        "api", "integration", "webhook", "sync", "import", "export",
        "third-party", "external", "erp", "crm", "payment", "gateway",
        "sso", "ldap", "oauth", "connect", "adapter",
    ],
    "data": [
        "migration", "large", "million", "billion", "historical", "archive",
        "report", "dashboard", "analytics", "aggregate", "data warehouse",
        "etl", "pipeline", "streaming", "real-time",
    ],
    "uncertainty": [
        "maybe", "possibly", "tbd", "unclear", "assume", "approximately",
        "if possible", "nice to have", "stretch goal", "phase 2",
        "future", "later", "pending", "depends on",
    ],
}

COMPLEXITY_LEVELS = ["trivial", "simple", "moderate", "complex", "very_complex"]


def analyze_complexity(title: str, description: str = "") -> ComplexityBreakdown:
    """Score complexity across 5 dimensions from text analysis."""
    text = f"{title} {description}".lower()
    scores = ComplexityBreakdown()

    for dim, keywords in COMPLEXITY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in text)
        base = min(matches * 15, 60)  # Up to 60 from keyword matches
        # Bonus for description length (more text = potentially more complex)
        length_bonus = min(len(description) / 200 * 10, 20) if description else 0
        setattr(scores, dim, min(base + length_bonus, 100))

    # Weighted overall
    weights = {"structural": 0.30, "domain": 0.20, "integration": 0.20, "data": 0.15, "uncertainty": 0.15}
    scores.overall = round(
        sum(getattr(scores, k) * w for k, w in weights.items()), 1
    )
    return scores


def complexity_level(score: float) -> str:
    if score < 15:
        return "trivial"
    elif score < 35:
        return "simple"
    elif score < 60:
        return "moderate"
    elif score < 80:
        return "complex"
    else:
        return "very_complex"
