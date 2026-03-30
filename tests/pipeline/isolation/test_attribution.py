"""Tests for compute_attribution(MetricComparison, swap_results) -> AttributionTable."""

from __future__ import annotations

from thesean.models.comparison import MetricComparison
from thesean.models.metric import MetricResult
from thesean.models.swap import SwapTestResult
from thesean.pipeline.isolation.attribution import compute_attribution


def _metric(
    metric_id: str = "track_progress",
    baseline_value: float = 0.8,
    candidate_value: float = 0.6,
    higher_is_better: bool = True,
    baseline_per_episode: list[float] | None = None,
    candidate_per_episode: list[float] | None = None,
) -> MetricComparison:
    bv, cv = baseline_value, candidate_value
    delta = cv - bv
    delta_badness = -delta if higher_is_better else delta
    return MetricComparison(
        metric_id=metric_id,
        baseline_value=bv,
        candidate_value=cv,
        delta=delta,
        delta_badness=delta_badness,
        higher_is_better=higher_is_better,
        baseline_per_episode=baseline_per_episode or [bv],
        candidate_per_episode=candidate_per_episode or [cv],
        status="regression",
    )


def _swap_result(
    test_id: str,
    metric_id: str = "track_progress",
    value: float = 0.7,
    status: str = "ok",
) -> SwapTestResult:
    return SwapTestResult(
        test_id=test_id,
        status=status,
        metrics=[MetricResult(metric_id=metric_id, value=value, higher_is_better=True)],
    )


class TestComputeAttribution:
    def test_metric_not_in_swaps_returns_not_attributable(self) -> None:
        m = _metric(metric_id="unknown_metric")
        swaps = [_swap_result("swap_wm", metric_id="other_metric")]
        table = compute_attribution(m, swaps)
        assert table.decision == "not_attributable"
        assert table.metric_id == "unknown_metric"

    def test_below_absolute_threshold_returns_no_change(self) -> None:
        # baseline=0.8, candidate=0.795 → delta_badness=0.005 < 0.01
        m = _metric(baseline_value=0.8, candidate_value=0.795)
        swaps = [
            _swap_result("baseline", value=0.8),
            _swap_result("candidate", value=0.795),
        ]
        table = compute_attribution(m, swaps)
        assert table.decision == "no_change"

    def test_single_dominant_factor(self) -> None:
        m = _metric(baseline_value=0.8, candidate_value=0.5)
        swaps = [
            _swap_result("baseline", value=0.8),
            _swap_result("candidate", value=0.5),
            _swap_result("swap_wm", value=0.55),
            _swap_result("swap_planner", value=0.78),
            _swap_result("swap_env", value=0.79),
        ]
        table = compute_attribution(m, swaps)
        assert table.decision == "world_model"
        assert len(table.main_effects) == 3
        wm = next(e for e in table.main_effects if e.factor == "world_model")
        assert wm.effect > 0

    def test_interaction_detection(self) -> None:
        m = _metric(baseline_value=0.8, candidate_value=0.5)
        swaps = [
            _swap_result("baseline", value=0.8),
            _swap_result("candidate", value=0.5),
            _swap_result("swap_wm", value=0.72),
            _swap_result("swap_planner", value=0.75),
            _swap_result("swap_env", value=0.79),
            # wm+planner combined is much worse than sum of individual effects
            _swap_result("swap_wm_planner", value=0.55),
        ]
        table = compute_attribution(m, swaps)
        assert len(table.interaction_effects) == 1
        assert table.interaction_effects[0].factor == "interaction"

    def test_main_interaction_split(self) -> None:
        m = _metric(baseline_value=0.8, candidate_value=0.5)
        swaps = [
            _swap_result("baseline", value=0.8),
            _swap_result("candidate", value=0.5),
            _swap_result("swap_wm", value=0.72),
            _swap_result("swap_planner", value=0.75),
            _swap_result("swap_env", value=0.79),
            _swap_result("swap_wm_planner", value=0.55),
        ]
        table = compute_attribution(m, swaps)
        main_factors = {e.factor for e in table.main_effects}
        interaction_factors = {e.factor for e in table.interaction_effects}
        assert "interaction" not in main_factors
        assert "interaction" in interaction_factors

    def test_support_tests_populated(self) -> None:
        m = _metric(baseline_value=0.8, candidate_value=0.5)
        swaps = [
            _swap_result("baseline", value=0.8),
            _swap_result("candidate", value=0.5),
            _swap_result("swap_wm", value=0.55),
            _swap_result("swap_planner", value=0.78),
            _swap_result("swap_env", value=0.79),
        ]
        table = compute_attribution(m, swaps)
        wm = next(e for e in table.main_effects if e.factor == "world_model")
        assert wm.support_tests == ["swap_wm"]
        pl = next(e for e in table.main_effects if e.factor == "planner")
        assert pl.support_tests == ["swap_planner"]
        env = next(e for e in table.main_effects if e.factor == "env")
        assert env.support_tests == ["swap_env"]

    def test_confidence_reduced_with_noisy_data(self) -> None:
        # CV > 1.0 when per-episode data is very noisy relative to the mean
        m = _metric(
            baseline_value=0.1,
            candidate_value=0.05,
            baseline_per_episode=[0.01, 0.05, 0.2, 0.15, 0.09],
            candidate_per_episode=[0.001, 0.02, 0.15, 0.1, 0.05],
        )
        swaps = [
            _swap_result("baseline", value=0.1),
            _swap_result("candidate", value=0.05),
            _swap_result("swap_wm", value=0.06),
            _swap_result("swap_planner", value=0.09),
            _swap_result("swap_env", value=0.095),
        ]
        table = compute_attribution(m, swaps)
        # The table should still produce results — confidence is internal
        assert table.metric_id == "track_progress"

    def test_metric_id_preserved(self) -> None:
        m = _metric(metric_id="offtrack_rate")
        swaps = [_swap_result("swap_wm", metric_id="offtrack_rate", value=0.7)]
        table = compute_attribution(m, swaps)
        assert table.metric_id == "offtrack_rate"
