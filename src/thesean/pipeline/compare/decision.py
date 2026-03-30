from __future__ import annotations

from thesean.models.comparison import ComparisonStatus


def classify_metric(
    delta_badness: float,
    ci_low: float | None,
    ci_high: float | None,
    p_adj: float,
    threshold: float = 0.01,
    alpha: float = 0.05,
) -> ComparisonStatus:
    if ci_low is None or ci_high is None:
        return "no_change"
    if delta_badness > threshold and ci_low > 0 and p_adj < alpha:
        return "regression"
    if delta_badness < -threshold and ci_high < 0 and p_adj < alpha:
        return "improvement"
    return "no_change"
