"""
Conductor Again — Risk Forecaster
Predicts project risks: schedule, technical, dependency, resource, quality.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class RiskItem:
    category: str = ""          # schedule, technical, dependency, resource, quality
    description: str = ""
    probability: float = 0.0    # 0-1
    impact: float = 0.0         # 0-1
    severity: float = 0.0       # probability × impact
    level: str = "low"          # low, medium, high, critical
    mitigation: str = ""
    affected_functions: list[str] = None


@dataclass
class RiskForecast:
    overall_risk_score: float = 0.0
    level: str = "low"
    items: list[RiskItem] = None
    schedule_buffer_days: int = 0
    summary: str = ""


RISK_PATTERNS = [
    {
        "category": "schedule",
        "pattern": ["deadline", "tight", "urgent", "asap", "critical path", "milestone", "release"],
        "probability": 0.6, "impact": 0.7,
        "mitigation": "Add 20% schedule buffer. Break into smaller deliverable increments.",
    },
    {
        "category": "technical",
        "pattern": ["new technology", "unfamiliar", "experimental", "poc", "prototype", "bleeding edge"],
        "probability": 0.5, "impact": 0.6,
        "mitigation": "Allocate spike/research time. Identify fallback technology.",
    },
    {
        "category": "dependency",
        "pattern": ["depends on", "requires", "blocked by", "waiting for", "external team", "third party"],
        "probability": 0.5, "impact": 0.7,
        "mitigation": "Identify dependency owners. Establish SLA and escalation path.",
    },
    {
        "category": "resource",
        "pattern": ["specialized", "expert", "only one person", "key person", "bus factor", "single point"],
        "probability": 0.4, "impact": 0.8,
        "mitigation": "Cross-train team. Document knowledge. Identify backup resource.",
    },
    {
        "category": "quality",
        "pattern": ["high volume", "data migration", "accuracy", "precision", "financial", "compliance", "audit"],
        "probability": 0.4, "impact": 0.7,
        "mitigation": "Add automated regression tests. Implement data validation checkpoints.",
    },
    {
        "category": "schedule",
        "pattern": ["all at once", "big bang", "cutover", "go-live", "launch"],
        "probability": 0.5, "impact": 0.6,
        "mitigation": "Plan phased rollout. Have rollback procedure ready.",
    },
]


def forecast_risks(functions: list[dict]) -> RiskForecast:
    """Analyze a function list and predict project risks."""
    items: list[RiskItem] = []

    for func in functions:
        title = func.get("title", "")
        desc = func.get("description", "")
        text = f"{title} {desc}".lower()

        for pattern in RISK_PATTERNS:
            matches = [p for p in pattern["pattern"] if p in text]
            if matches:
                item = RiskItem(
                    category=pattern["category"],
                    description=f"'{title}': matched risk pattern(s): {', '.join(matches)}",
                    probability=pattern["probability"],
                    impact=pattern["impact"],
                    severity=round(pattern["probability"] * pattern["impact"], 2),
                    mitigation=pattern["mitigation"],
                    affected_functions=[title],
                )
                # Severity level
                if item.severity >= 0.5:
                    item.level = "critical"
                elif item.severity >= 0.35:
                    item.level = "high"
                elif item.severity >= 0.20:
                    item.level = "medium"
                else:
                    item.level = "low"
                items.append(item)

    # Deduplicate and merge similar risks
    merged = _merge_risks(items)

    # Overall score
    if merged:
        overall = round(sum(r.severity for r in merged) / len(merged), 2)
    else:
        overall = 0.1

    if overall >= 0.5:
        level = "critical"
        schedule_buffer = 30
        summary = "High risk project. Recommend phased delivery with frequent checkpoints."
    elif overall >= 0.35:
        level = "high"
        schedule_buffer = 20
        summary = "Several risk factors identified. Add buffer and monitor closely."
    elif overall >= 0.20:
        level = "medium"
        schedule_buffer = 10
        summary = "Manageable risk profile. Standard mitigation recommended."
    else:
        level = "low"
        schedule_buffer = 5
        summary = "Low risk. Standard project management practices sufficient."

    return RiskForecast(
        overall_risk_score=overall,
        level=level,
        items=merged,
        schedule_buffer_days=schedule_buffer,
        summary=summary,
    )


def _merge_risks(items: list[RiskItem]) -> list[RiskItem]:
    """Merge risks with same category."""
    by_cat: dict[str, RiskItem] = {}
    for item in items:
        if item.category not in by_cat:
            by_cat[item.category] = item
        else:
            existing = by_cat[item.category]
            existing.probability = max(existing.probability, item.probability)
            existing.impact = max(existing.impact, item.impact)
            existing.severity = round(existing.probability * existing.impact, 2)
            existing.affected_functions = list(set(existing.affected_functions or []) | set(item.affected_functions or []))
            # Upgrade level if severity increased
            if existing.severity >= 0.5:
                existing.level = "critical"
            elif existing.severity >= 0.35:
                existing.level = "high"
    return sorted(by_cat.values(), key=lambda r: r.severity, reverse=True)
