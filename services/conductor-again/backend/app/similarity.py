"""
Conductor Again — Similarity Engine
Detects related/duplicate functions using keyword overlap + semantic heuristics.
"""

from dataclasses import dataclass
from math import sqrt


@dataclass
class SimilarityResult:
    score: float = 0.0               # 0-1 similarity
    level: str = "none"              # none, low, medium, high, duplicate
    shared_keywords: list[str] = None
    shared_domain: bool = False
    recommendation: str = ""


def tokenize(text: str) -> set[str]:
    """Simple tokenization: lowercase, split, filter short words."""
    stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "shall",
            "should", "may", "might", "must", "can", "could", "and", "or", "not",
            "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
            "into", "through", "during", "before", "after", "above", "below",
            "between", "under", "this", "that", "these", "those", "it", "its",
            "the", "system", "user", "need", "want", "able", "allow", "must"}
    words = text.lower().replace(",", " ").replace(".", " ").replace("/", " ").split()
    return {w for w in words if len(w) > 3 and w not in stop}


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def cosine_similarity(set_a: set[str], set_b: set[str]) -> float:
    # Approximate cosine using shared token frequency
    all_terms = set_a | set_b
    if not all_terms:
        return 0.0
    vec_a = [1 if t in set_a else 0 for t in all_terms]
    vec_b = [1 if t in set_b else 0 for t in all_terms]
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = sqrt(sum(a * a for a in vec_a))
    mag_b = sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def analyze_similarity(title_a: str, desc_a: str, title_b: str, desc_b: str) -> SimilarityResult:
    """Compute similarity between two functions."""
    tokens_a = tokenize(f"{title_a} {desc_a}")
    tokens_b = tokenize(f"{title_b} {desc_b}")

    jaccard = jaccard_similarity(tokens_a, tokens_b)
    cosine = cosine_similarity(tokens_a, tokens_b)
    shared = sorted(tokens_a & tokens_b)

    # Combined score
    score = round(0.5 * jaccard + 0.5 * cosine, 3)

    # Level
    if score > 0.85:
        level = "duplicate"
        rec = "Consider merging — these functions appear identical."
    elif score > 0.65:
        level = "high"
        rec = "High overlap detected. Review for consolidation."
    elif score > 0.40:
        level = "medium"
        rec = "Moderate similarity — may share components or tests."
    elif score > 0.20:
        level = "low"
        rec = "Some shared concepts. Potential shared test scenarios."
    else:
        level = "none"
        rec = ""

    return SimilarityResult(
        score=score,
        level=level,
        shared_keywords=shared[:10],
        recommendation=rec,
    )
