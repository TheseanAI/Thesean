"""Unit tests for pipeline.compare_module — pure comparison logic."""

import pytest

from thesean.models.episode import EpisodeOutcome, EpisodeRecord
from thesean.pipeline.compare_module import (
    CompareResult,
    MetricResult,
    build_episode_outcome,
    compare_results,
)


def _make_outcome(
    side: str,
    mean_progress: float = 0.5,
    completion_rate: float = 0.5,
    mean_reward: float = 50.0,
    off_track_rate: float = 0.1,
    fastest_lap: float | None = None,
) -> EpisodeOutcome:
    """Build a synthetic EpisodeOutcome for testing."""
    return EpisodeOutcome(
        side=side,
        episodes=[
            EpisodeRecord(episode_idx=0, final_track_progress=mean_progress, total_reward=mean_reward)
        ],
        mean_progress=mean_progress,
        completion_rate=completion_rate,
        mean_reward=mean_reward,
        off_track_rate=off_track_rate,
        fastest_lap=fastest_lap,
    )


def _make_raw(reward: float = 50.0) -> list[dict]:
    return [{"episode_idx": 0, "total_reward": reward}]


class TestBuildEpisodeOutcome:
    def test_single_episode(self):
        result = build_episode_outcome(
            "a",
            [{"episode_idx": 0, "final_track_progress": 0.8, "total_reward": 100.0}],
        )
        assert isinstance(result, EpisodeOutcome)
        assert result.side == "a"
        assert result.mean_progress == pytest.approx(0.8)
        assert result.mean_reward == pytest.approx(100.0)

    def test_multiple_episodes_averages(self):
        raw = [
            {"episode_idx": 0, "final_track_progress": 0.6, "total_reward": 80.0},
            {"episode_idx": 1, "final_track_progress": 1.0, "total_reward": 120.0},
        ]
        result = build_episode_outcome("b", raw)
        assert result.mean_progress == pytest.approx(0.8)
        assert result.mean_reward == pytest.approx(100.0)
        assert result.completion_rate == pytest.approx(1.0)  # no termination = completed

    def test_off_track_rate(self):
        raw = [
            {"episode_idx": 0, "termination": "off_track"},
            {"episode_idx": 1, "termination": None},
        ]
        result = build_episode_outcome("a", raw)
        assert result.off_track_rate == pytest.approx(0.5)

    def test_fastest_lap(self):
        raw = [
            {"episode_idx": 0, "fastest_lap_time": 30.5},
            {"episode_idx": 1, "fastest_lap_time": 28.2},
        ]
        result = build_episode_outcome("a", raw)
        assert result.fastest_lap == pytest.approx(28.2)

    def test_no_fastest_lap(self):
        raw = [{"episode_idx": 0}]
        result = build_episode_outcome("a", raw)
        assert result.fastest_lap is None


class TestCompareResults:
    def test_regression_detected(self):
        """Candidate worse than baseline -> regression."""
        outcome_a = _make_outcome("a", mean_progress=0.9, mean_reward=100.0)
        outcome_b = _make_outcome("b", mean_progress=0.5, mean_reward=40.0)
        result = compare_results(outcome_a, outcome_b, _make_raw(100.0), _make_raw(40.0))
        assert isinstance(result, CompareResult)
        assert result.verdict == "regression"
        assert result.regression_count > 0

    def test_no_change(self):
        """Identical outcomes -> no_change."""
        outcome_a = _make_outcome("a", mean_progress=0.5, mean_reward=50.0, off_track_rate=0.1)
        outcome_b = _make_outcome("b", mean_progress=0.5, mean_reward=50.0, off_track_rate=0.1)
        result = compare_results(outcome_a, outcome_b, _make_raw(50.0), _make_raw(50.0))
        assert result.verdict == "no_change"

    def test_improvement_detected(self):
        """Candidate outperforms baseline -> improvement."""
        outcome_a = _make_outcome("a", mean_progress=0.5, mean_reward=40.0)
        outcome_b = _make_outcome("b", mean_progress=0.9, mean_reward=100.0)
        result = compare_results(outcome_a, outcome_b, _make_raw(40.0), _make_raw(100.0))
        assert result.verdict == "improvement"
        assert result.improvement_count > 0

    def test_fastest_lap_included_when_both_present(self):
        """fastest_lap metric included when both sides have data."""
        outcome_a = _make_outcome("a", fastest_lap=30.0)
        outcome_b = _make_outcome("b", fastest_lap=25.0)
        result = compare_results(outcome_a, outcome_b, _make_raw(), _make_raw())
        metric_ids = [m.metric_id for m in result.metrics]
        assert "fastest_lap_time" in metric_ids

    def test_fastest_lap_excluded_when_one_missing(self):
        """fastest_lap metric excluded when one side missing."""
        outcome_a = _make_outcome("a", fastest_lap=30.0)
        outcome_b = _make_outcome("b", fastest_lap=None)
        result = compare_results(outcome_a, outcome_b, _make_raw(), _make_raw())
        metric_ids = [m.metric_id for m in result.metrics]
        assert "fastest_lap_time" not in metric_ids

    def test_compare_result_has_required_fields(self):
        """CompareResult has all required raw data fields with valid values."""
        outcome_a = _make_outcome("a")
        outcome_b = _make_outcome("b")
        result = compare_results(outcome_a, outcome_b, _make_raw(), _make_raw())
        assert result.verdict in ("regression", "improvement", "no_change", "mixed")
        assert isinstance(result.primary_metric, str) and len(result.primary_metric) > 0
        assert isinstance(result.baseline_value, float)
        assert isinstance(result.candidate_value, float)
        assert isinstance(result.delta_pct, float)
        assert isinstance(result.significant, bool)
        assert isinstance(result.regression_count, int) and result.regression_count >= 0
        assert isinstance(result.improvement_count, int) and result.improvement_count >= 0
        assert isinstance(result.no_change_count, int) and result.no_change_count >= 0
        assert isinstance(result.metrics, list)
        assert len(result.metrics) > 0
        for m in result.metrics:
            assert isinstance(m, MetricResult)
            assert m.status in ("regression", "improvement", "no_change")

    def test_compare_result_no_display_strings(self):
        """CompareResult does NOT have display string fields (D-01)."""
        assert not hasattr(CompareResult, "verdict_headline")
        fields = CompareResult.model_fields
        assert "verdict_headline" not in fields
        assert "primary_metric_line" not in fields
        assert "findings_count_line" not in fields

    def test_top_run_and_recommended(self):
        """top_run and recommended_run_ids computed from raw episodes."""
        raw_a = [
            {"episode_idx": 0, "total_reward": 100.0},
            {"episode_idx": 1, "total_reward": 50.0},
        ]
        raw_b = [
            {"episode_idx": 0, "total_reward": 80.0},
            {"episode_idx": 1, "total_reward": 10.0},
        ]
        outcome_a = _make_outcome("a")
        outcome_b = _make_outcome("b")
        result = compare_results(outcome_a, outcome_b, raw_a, raw_b)
        assert result.top_run is not None
        assert "episode_id" in result.top_run
        assert len(result.recommended_run_ids) > 0
