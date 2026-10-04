"""Route Score and Data Confidence. Deterministic: no AI, no invented numbers.

A factor with no recorded evidence is left out of the average — it is never
scored as zero.
"""


def compute_score(lighting_score: float | None, activity_score: float | None) -> float | None:
    """0-100, or None when neither factor has any evidence."""
    factors = [f for f in (lighting_score, activity_score) if f is not None]
    if not factors:
        return None
    return round(100 * sum(factors) / len(factors), 1)


def compute_confidence(lighting_coverage: float, activity_coverage: float, has_scores: bool) -> str:
    """Low/Medium/High from the weaker of the two evidence-coverage fractions."""
    if not has_scores:
        return "Low"
    weakest = min(lighting_coverage, activity_coverage)
    if weakest < 0.1:
        return "Low"
    if weakest < 0.5:
        return "Medium"
    return "High"
