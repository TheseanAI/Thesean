"""Compute attribution from swap test results."""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from thesean.models.comparison import MetricComparison
from thesean.models.isolation import AttributionTable, EffectEstimate
from thesean.models.swap import SwapTestResult

ABSOLUTE_THRESHOLD = 0.01

_SUPPORT_TESTS = {
    "world_model": ["swap_wm"],
    "planner": ["swap_planner"],
    "env": ["swap_env"],
    "interaction": ["swap_wm_planner"],
}

class _FactorScore(NamedTuple):
    factor: str
    score: float
    effect_badness: float
    confidence: float


def compute_attribution(
    metric: MetricComparison,
    swap_results: list[SwapTestResult],
) -> AttributionTable:
    """Score factors from swap test deltas for a given metric comparison."""
    metric_id = metric.metric_id
    higher_is_better = metric.higher_is_better

    # Check if this metric is available in any swap result
    metric_in_swaps = any(
        m.metric_id == metric_id
        for sr in swap_results
        if sr.status == "ok"
        for m in sr.metrics
    )
    if not metric_in_swaps:
        return AttributionTable(
            metric_id=metric_id,
            main_effects=[EffectEstimate(
                factor="unknown", effect=0.0, confidence=0.0,
                support_tests=[],
            )],
            interaction_effects=[],
            decision="not_attributable",
        )

    def badness(value: float) -> float:
        return -value if higher_is_better else value

    # Extract metric values from swap results
    def get_metric_value(test_id: str) -> float | None:
        for sr in swap_results:
            if sr.test_id == test_id and sr.status == "ok":
                for m in sr.metrics:
                    if m.metric_id == metric_id:
                        return m.value
        return None

    baseline_val = get_metric_value("baseline")
    candidate_val = get_metric_value("candidate")

    # Fallback to metric values if identity tests weren't run separately
    if baseline_val is None:
        baseline_val = metric.baseline_value
    if candidate_val is None:
        candidate_val = metric.candidate_value

    delta_total = badness(candidate_val) - badness(baseline_val)

    # Gate on absolute threshold
    if delta_total <= ABSOLUTE_THRESHOLD:
        return AttributionTable(
            metric_id=metric_id,
            main_effects=[EffectEstimate(
                factor="unknown", effect=delta_total, confidence=0.0,
                support_tests=[],
            )],
            interaction_effects=[],
            decision="no_change",
        )

    # Main effects
    factors: list[_FactorScore] = []
    main_effect_count = 0

    for factor_name, test_id in [
        ("world_model", "swap_wm"),
        ("planner", "swap_planner"),
        ("env", "swap_env"),
    ]:
        val = get_metric_value(test_id)
        if val is None:
            continue
        main_effect_count += 1
        delta_f = badness(val) - badness(baseline_val)
        score = max(0.0, min(1.0, delta_f / delta_total))
        factors.append(_FactorScore(
            factor=factor_name,
            score=score,
            effect_badness=delta_f,
            confidence=score,  # placeholder, modulated by overall_confidence below
        ))

    # Interaction check
    interaction_factors: list[_FactorScore] = []
    wm_planner_val = get_metric_value("swap_wm_planner")
    if wm_planner_val is not None:
        delta_wm_planner = badness(wm_planner_val) - badness(baseline_val)
        delta_wm = next((f.effect_badness for f in factors if f.factor == "world_model"), 0.0)
        delta_p = next((f.effect_badness for f in factors if f.factor == "planner"), 0.0)
        interaction = delta_wm_planner - delta_wm - delta_p

        if delta_total > ABSOLUTE_THRESHOLD and interaction > 0.15 * delta_total:
            interaction_score = max(0.0, min(1.0, interaction / delta_total))
            interaction_factors.append(_FactorScore(
                factor="interaction",
                score=interaction_score,
                effect_badness=interaction,
                confidence=0.8,
            ))

    # Confidence — use real within-group CV (worst-case noisiness)
    c_coverage = main_effect_count / 3.0
    b_eps = metric.baseline_per_episode
    c_eps = metric.candidate_per_episode
    cv_b = float(np.std(b_eps) / abs(np.mean(b_eps))
                 if b_eps and abs(np.mean(b_eps)) > 1e-9 else 0.0)
    cv_c = float(np.std(c_eps) / abs(np.mean(c_eps))
                 if c_eps and abs(np.mean(c_eps)) > 1e-9 else 0.0)
    cv = max(cv_b, cv_c)
    c_consistency = 0.7 if cv > 1.0 else 1.0
    overall_confidence = max(0.0, min(1.0, c_coverage * c_consistency))

    # Modulate per-factor confidence by overall confidence
    factors = [
        _FactorScore(
            factor=f.factor,
            score=f.score,
            effect_badness=f.effect_badness,
            confidence=max(0.0, min(1.0, f.confidence * overall_confidence)),
        )
        for f in factors
    ]

    # Rank and decide
    all_factors = factors + interaction_factors
    all_factors.sort(key=lambda f: f.score, reverse=True)

    if not all_factors or all_factors[0].score < 0.35 or main_effect_count < 2:
        decision = "unknown"
    else:
        decision = all_factors[0].factor

    # Build EffectEstimate lists split by main vs interaction
    main_effects = [
        EffectEstimate(
            factor=f.factor,
            effect=f.effect_badness,
            confidence=f.confidence,
            support_tests=_SUPPORT_TESTS.get(f.factor, []),
        )
        for f in all_factors if f.factor != "interaction"
    ]
    interaction_effects = [
        EffectEstimate(
            factor=f.factor,
            effect=f.effect_badness,
            confidence=f.confidence,
            support_tests=_SUPPORT_TESTS.get(f.factor, []),
        )
        for f in all_factors if f.factor == "interaction"
    ]

    return AttributionTable(
        metric_id=metric_id,
        main_effects=main_effects,
        interaction_effects=interaction_effects,
        decision=decision,
    )
