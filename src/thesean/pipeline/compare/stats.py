from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import bootstrap, permutation_test
from statsmodels.stats.multitest import multipletests


def paired_mean_diff(x: np.ndarray, y: np.ndarray, axis: int = 0) -> Any:
    return np.mean(y - x, axis=axis)


def bootstrap_ci(
    baseline_vals: list[float],
    candidate_vals: list[float],
    n_resamples: int = 5000,
) -> tuple[float, float]:
    x = np.asarray(baseline_vals, dtype=float)
    y = np.asarray(candidate_vals, dtype=float)
    n = min(len(x), len(y))
    if n < 2:
        # Cannot compute CI with fewer than 2 observations
        return (float("nan"), float("nan"))
    res = bootstrap(
        (x[:n], y[:n]),
        paired_mean_diff,
        paired=True,
        confidence_level=0.95,
        n_resamples=n_resamples,
        method="BCa",
        rng=np.random.default_rng(12345),
    )
    return float(res.confidence_interval.low), float(res.confidence_interval.high)


def paired_pvalue(
    baseline_vals: list[float],
    candidate_vals: list[float],
    n_resamples: int = 5000,
) -> float:
    x = np.asarray(baseline_vals, dtype=float)
    y = np.asarray(candidate_vals, dtype=float)
    n = min(len(x), len(y))
    if n < 2:
        return 1.0
    res = permutation_test(
        (x[:n], y[:n]),
        paired_mean_diff,
        permutation_type="samples",
        alternative="two-sided",
        n_resamples=n_resamples,
        rng=np.random.default_rng(12345),
    )
    return float(res.pvalue)


def adjust_pvalues(pvals: list[float], alpha: float = 0.05) -> list[float]:
    _, adj, _, _ = multipletests(pvals, alpha=alpha, method="holm")
    return [float(v) for v in adj]
