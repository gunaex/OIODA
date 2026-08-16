"""Deterministic Bottleneck Analysis.

No LLM required. Uses normalized metric aggregation.
"""

from __future__ import annotations

from .models import FlowBottleneck, FlowMetric, FlowPlaybackState, Severity, MetricSource, FlowNodeState


def analyze_bottlenecks(
    state: FlowPlaybackState,
    metrics: dict[str, list[FlowMetric]] | None = None,
) -> list[FlowBottleneck]:
    """Compute bottlenecks from node metrics.

    Uses deterministic weighted aggregation of latency, throughput,
    error rate, and dependency pressure.
    """
    if not metrics:
        return list(state.bottlenecks) if state.bottlenecks else []

    bottlenecks: list[FlowBottleneck] = []
    for node_id, node_metrics in metrics.items():
        score = _compute_bottleneck_score(node_metrics)
        if score is None or score < 30:
            continue

        severity = Severity.INFO
        if score >= 80:
            severity = Severity.CRITICAL
        elif score >= 60:
            severity = Severity.HIGH
        elif score >= 40:
            severity = Severity.WARNING

        factors = [
            {"type": m.name.upper(), "value": m.value, "unit": m.unit, "source": m.source.value}
            for m in node_metrics
        ]

        dominant = max(factors, key=lambda f: f["value"]) if factors else {"type": "UNKNOWN", "value": 0}
        explanation = (
            f"{node_id} is a bottleneck: {dominant['type']} at {dominant['value']}{dominant.get('unit','')}"
        )

        bottlenecks.append(FlowBottleneck(
            node_id=node_id, score=score, severity=severity,
            factors=factors, explanation=explanation,
        ))

    bottlenecks.sort(key=lambda b: b.score or 0, reverse=True)
    return bottlenecks


def _compute_bottleneck_score(metrics: list[FlowMetric]) -> float | None:
    """Weighted deterministic aggregation.

    Normalizes latency (0-1000ms → 0-100), throughput (0-1000 req/s → 0-100),
    error rate (0-100% → 0-100), dependency wait (as-is).
    """
    if not metrics:
        return None

    weights = {"latency": 0.4, "throughput": 0.2, "error_rate": 0.25, "dependency_wait": 0.15}
    score = 0.0
    total_weight = 0.0

    for m in metrics:
        w = weights.get(m.name, 0.1)
        norm = _normalize_metric(m)
        score += norm * w
        total_weight += w

    if total_weight == 0:
        return None

    return min(100.0, (score / total_weight) * 100)


def _normalize_metric(m: FlowMetric) -> float:
    """Normalize metric value to 0-1 range."""
    if m.name == "latency":
        return min(1.0, m.value / 1000.0)  # 1000ms = max
    if m.name == "throughput":
        return 1.0 - min(1.0, m.value / 1000.0)  # lower throughput = more bottleneck
    if m.name == "error_rate":
        return min(1.0, m.value / 100.0)
    if m.name == "dependency_wait":
        return min(1.0, m.value / 5000.0)
    return 0.0
