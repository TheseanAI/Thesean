"""Tests for Phase 2 episode models: EpisodeRecord, EpisodeOutcome, OutcomeSummary."""

from __future__ import annotations

import json

from thesean.models.episode import (
    METRIC_DISPLAY_NAMES,
    EpisodeRecord,
    OutcomeSummary,
)

# ── EpisodeRecord ────────────────────────────────────────────────────────────

class TestEpisodeRecord:
    def test_completed_true_when_termination_is_none(self):
        ep = EpisodeRecord(
            episode_idx=0,
            final_track_progress=0.95,
            total_reward=400.0,
            termination=None,
            fastest_lap_time=42.3,
            lap_count=1,
            completed=True,
        )
        assert ep.completed is True

    def test_completed_true_when_termination_lap_complete(self):
        ep = EpisodeRecord(
            episode_idx=1,
            final_track_progress=1.0,
            total_reward=500.0,
            termination="lap_complete",
            fastest_lap_time=38.9,
            lap_count=1,
            completed=True,
        )
        assert ep.completed is True

    def test_completed_false_when_termination_off_track(self):
        ep = EpisodeRecord(
            episode_idx=2,
            final_track_progress=0.45,
            total_reward=100.0,
            termination="off_track",
            fastest_lap_time=None,
            lap_count=0,
            completed=False,
        )
        assert ep.completed is False

    def test_defaults(self):
        ep = EpisodeRecord(
            episode_idx=3,
            final_track_progress=0.5,
            total_reward=200.0,
        )
        assert ep.termination is None
        assert ep.fastest_lap_time is None
        assert ep.lap_count == 0


# ── OutcomeSummary ───────────────────────────────────────────────────────────

class TestOutcomeSummary:
    def _make_summary(self) -> OutcomeSummary:
        return OutcomeSummary(
            verdict="regression",
            primary_metric="final_track_progress",
            primary_metric_display="completion",
            baseline_value=0.78,
            candidate_value=0.45,
            delta_pct=-42.3,
            significant=True,
            regression_count=2,
            improvement_count=0,
            no_change_count=1,
            verdict_headline=(
                "Candidate underperformed baseline under the same planner setup."
            ),
            primary_metric_line="completion: candidate 45% vs baseline 78% (-42.3%)",
            findings_count_line="2 metrics regressed",
        )

    def test_roundtrip_model_dump_json(self):
        summary = self._make_summary()
        json_str = summary.model_dump_json()
        summary2 = OutcomeSummary.model_validate_json(json_str)
        assert summary2 == summary

    def test_roundtrip_via_dict(self):
        summary = self._make_summary()
        raw = json.loads(summary.model_dump_json())
        summary2 = OutcomeSummary.model_validate(raw)
        assert summary2.verdict == "regression"
        assert summary2.primary_metric == "final_track_progress"
        assert summary2.regression_count == 2

    def test_verdict_literals(self):
        """All 4 verdict values are accepted."""
        for verdict in ("regression", "improvement", "no_change", "mixed"):
            s = OutcomeSummary(
                verdict=verdict,
                primary_metric="final_track_progress",
                primary_metric_display="completion",
                baseline_value=0.7,
                candidate_value=0.8,
                delta_pct=14.3,
                significant=True,
                regression_count=0,
                improvement_count=1,
                no_change_count=0,
                verdict_headline="headline",
                primary_metric_line="line",
                findings_count_line="count",
            )
            assert s.verdict == verdict


# ── METRIC_DISPLAY_NAMES ─────────────────────────────────────────────────────

class TestMetricDisplayNames:
    def test_known_keys_present(self):
        assert "final_track_progress" in METRIC_DISPLAY_NAMES
        assert "off_track_rate" in METRIC_DISPLAY_NAMES
        assert "total_reward" in METRIC_DISPLAY_NAMES
        assert "fastest_lap_time" in METRIC_DISPLAY_NAMES

    def test_display_values(self):
        assert METRIC_DISPLAY_NAMES["final_track_progress"] == "completion"
        assert METRIC_DISPLAY_NAMES["off_track_rate"] == "off-track rate"
