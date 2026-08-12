"""
Conductor Again — Effort Estimator
Function-point-inspired estimation: size × complexity × team factor.
"""

from dataclasses import dataclass

from app.complexity import complexity_level


@dataclass
class EffortEstimate:
    function_points: float = 0.0
    person_days: float = 0.0
    confidence: float = 0.7         # 0-1 based on input quality
    level: str = "small"           # small, medium, large, x-large
    breakdown: dict = None         # Design, Dev, Test, Docs breakdown
    assumptions: list[str] = None


# Function point weights by complexity level
FP_WEIGHTS = {
    "trivial":      2,
    "simple":       5,
    "moderate":     10,
    "complex":      20,
    "very_complex": 35,
}

# Person-days per function point (team velocity factor)
PD_PER_FP = 0.8  # Can be calibrated per team


def estimate_effort(
    title: str,
    description: str = "",
    complexity_score: float = 30.0,
    team_size: int = 1,
    has_existing_code: bool = False,
) -> EffortEstimate:
    """Estimate effort in function points and person-days."""
    level = complexity_level(complexity_score)
    fp = FP_WEIGHTS.get(level, 10)

    # Adjust for description detail
    if len(description) < 20:
        confidence = 0.5
        fp *= 1.3  # Buffer for uncertainty
        assumptions = ["Limited description — estimate has high uncertainty"]
    elif len(description) < 100:
        confidence = 0.7
        assumptions = ["Moderate detail — estimate should be refined"]
    else:
        confidence = 0.85
        assumptions = []

    # Adjust for existing code
    if has_existing_code:
        fp *= 0.7
        assumptions.append("Existing codebase reduces effort")

    # Calculate person-days
    pd = round(fp * PD_PER_FP, 1)

    # Parallelization factor
    if team_size > 1:
        pd = round(pd / min(team_size, 3), 1)  # Max 3x parallel speedup

    # Level
    if pd < 2:
        effort_level = "small"
    elif pd < 8:
        effort_level = "medium"
    elif pd < 20:
        effort_level = "large"
    else:
        effort_level = "x-large"

    # Breakdown
    breakdown = {
        "design": round(pd * 0.15, 1),
        "development": round(pd * 0.50, 1),
        "testing": round(pd * 0.25, 1),
        "documentation": round(pd * 0.10, 1),
    }

    return EffortEstimate(
        function_points=fp,
        person_days=pd,
        confidence=confidence,
        level=effort_level,
        breakdown=breakdown,
        assumptions=assumptions,
    )
