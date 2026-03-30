"""Tests for comparison schema: MetricComparison and ComparisonReport."""

from __future__ import annotations

from thesean.models.comparison import ComparisonReport, MetricComparison


class TestMetricComparison:
    def test_validates_with_all_fields(self) -> None:
        mc = MetricComparison(
            metric_id="track_progress",
            baseline_value=0.85,
            candidate_value=0.80,
            delta=-0.05,
            delta_badness=0.05,
            higher_is_better=True,
            baseline_per_episode=[0.8, 0.9],
            candidate_per_episode=[0.75, 0.85],
            ci_low=0.01,
            ci_high=0.09,
            p_value=0.02,
            p_value_adj=0.04,
            significant=True,
            status="regression",
        )
        assert mc.metric_id == "track_progress"
        assert mc.higher_is_better is True
        assert len(mc.baseline_per_episode) == 2
        assert mc.significant is True

    def test_defaults(self) -> None:
        mc = MetricComparison(
            metric_id="test",
            baseline_value=1.0,
            candidate_value=1.0,
            delta=0.0,
            delta_badness=0.0,
            higher_is_better=True,
            status="no_change",
        )
        assert mc.baseline_per_episode == []
        assert mc.candidate_per_episode == []
        assert mc.ci_low is None
        assert mc.ci_high is None
        assert mc.p_value is None
        assert mc.p_value_adj is None
        assert mc.significant is False


class TestComparisonReport:
    def test_json_round_trip(self) -> None:
        report = ComparisonReport(
            baseline_run_dir="/tmp/baseline",
            candidate_run_dir="/tmp/candidate",
            metrics=[
                MetricComparison(
                    metric_id="track_progress",
                    baseline_value=0.85,
                    candidate_value=0.80,
                    delta=-0.05,
                    delta_badness=0.05,
                    higher_is_better=True,
                    baseline_per_episode=[0.8, 0.9],
                    candidate_per_episode=[0.75, 0.85],
                    ci_low=0.01,
                    ci_high=0.09,
                    p_value=0.02,
                    p_value_adj=0.04,
                    significant=True,
                    status="regression",
                ),
            ],
        )
        json_str = report.model_dump_json()
        loaded = ComparisonReport.model_validate_json(json_str)
        assert loaded.baseline_run_dir == "/tmp/baseline"
        assert len(loaded.metrics) == 1
        assert loaded.metrics[0].metric_id == "track_progress"
        assert loaded.metrics[0].baseline_per_episode == [0.8, 0.9]
        assert loaded.metrics[0].significant is True

    def test_empty_metrics(self) -> None:
        report = ComparisonReport(
            baseline_run_dir="/tmp/b",
            candidate_run_dir="/tmp/c",
            metrics=[],
        )
        assert report.metrics == []
        loaded = ComparisonReport.model_validate_json(report.model_dump_json())
        assert loaded.metrics == []
