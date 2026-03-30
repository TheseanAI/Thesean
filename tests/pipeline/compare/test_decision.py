"""Tests for compare decision logic: classify_metric."""

from __future__ import annotations

from thesean.pipeline.compare.decision import classify_metric


class TestClassifyMetric:
    def test_regression(self) -> None:
        result = classify_metric(
            delta_badness=0.05,
            ci_low=0.02,
            ci_high=0.08,
            p_adj=0.01,
        )
        assert result == "regression"

    def test_improvement(self) -> None:
        result = classify_metric(
            delta_badness=-0.05,
            ci_low=-0.08,
            ci_high=-0.02,
            p_adj=0.01,
        )
        assert result == "improvement"

    def test_no_change_ci_crosses_zero(self) -> None:
        result = classify_metric(
            delta_badness=0.05,
            ci_low=-0.01,
            ci_high=0.08,
            p_adj=0.01,
        )
        assert result == "no_change"

    def test_no_change_not_significant(self) -> None:
        result = classify_metric(
            delta_badness=0.05,
            ci_low=0.02,
            ci_high=0.08,
            p_adj=0.10,
        )
        assert result == "no_change"

    def test_no_change_below_threshold(self) -> None:
        result = classify_metric(
            delta_badness=0.005,
            ci_low=0.001,
            ci_high=0.009,
            p_adj=0.01,
        )
        assert result == "no_change"

    def test_threshold_boundary_exactly_at(self) -> None:
        """delta_badness == threshold should be no_change (not >)."""
        result = classify_metric(
            delta_badness=0.01,
            ci_low=0.005,
            ci_high=0.015,
            p_adj=0.01,
        )
        assert result == "no_change"

    def test_custom_threshold(self) -> None:
        result = classify_metric(
            delta_badness=0.005,
            ci_low=0.001,
            ci_high=0.009,
            p_adj=0.01,
            threshold=0.001,
        )
        assert result == "regression"

    def test_custom_alpha(self) -> None:
        result = classify_metric(
            delta_badness=0.05,
            ci_low=0.02,
            ci_high=0.08,
            p_adj=0.08,
            alpha=0.10,
        )
        assert result == "regression"
