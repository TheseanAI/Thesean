"""Hypothesis property tests for core model invariants (INV-1-*)."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from thesean.models.comparison import MetricComparison
from thesean.models.episode import EpisodeRecord, OutcomeSummary
from thesean.models.event import Event
from tests.models.conftest import make_event, make_metric_comparison, make_outcome_summary

# ── Strategies ──────────────────────────────────────────────────────────

st_severity = st.sampled_from(["info", "warning", "critical"])
st_event_type = st.sampled_from([
    "first_signal_divergence", "first_action_divergence", "first_risk_spike",
    "first_boundary_collapse", "terminal", "max_metric_gap",
    "first_divergence", "divergence_window", "risk_spike",
    "off_track_terminal", "max_gap",
])
st_verdict = st.sampled_from(["regression", "improvement", "no_change", "mixed"])
st_status = st.sampled_from(["regression", "improvement", "no_change"])


# ── INV-1-1: MetricComparison per_episode lists same length ─────────

@pytest.mark.property
class TestMetricComparisonProperties:

    @given(
        n=st.integers(min_value=0, max_value=50),
    )
    @settings(max_examples=200)
    def test_per_episode_same_length(self, n: int) -> None:
        """INV-1-1: baseline/candidate per_episode lists must have same length."""
        baseline = [float(i) for i in range(n)]
        candidate = [float(i) for i in range(n)]
        mc = MetricComparison(
            metric_id="test",
            baseline_value=0.5,
            candidate_value=0.6,
            delta=0.1,
            delta_badness=0.1,
            higher_is_better=True,
            status="improvement",
            baseline_per_episode=baseline,
            candidate_per_episode=candidate,
        )
        assert len(mc.baseline_per_episode) == len(mc.candidate_per_episode)


# ── INV-1-7: Event.step >= 0 ────────────────────────────────────────

@pytest.mark.property
class TestEventProperties:

    @given(step=st.integers(min_value=0, max_value=10000))
    @settings(max_examples=200)
    def test_step_non_negative(self, step: int) -> None:
        """INV-1-7: Event.step >= 0."""
        evt = make_event(step=step)
        assert evt.step >= 0

    @given(k=st.integers(min_value=1, max_value=100))
    @settings(max_examples=200)
    def test_persistence_k_at_least_one(self, k: int) -> None:
        """INV-1-8: Event.persistence_k >= 1."""
        evt = make_event(persistence_k=k)
        assert evt.persistence_k >= 1


# ── INV-1-10: OutcomeSummary partition invariant ─────────────────────

@pytest.mark.property
class TestOutcomeSummaryProperties:

    @given(
        regression=st.integers(min_value=0, max_value=20),
        improvement=st.integers(min_value=0, max_value=20),
        no_change=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=200)
    def test_counts_sum_to_total(self, regression: int, improvement: int, no_change: int) -> None:
        """INV-1-10: regression + improvement + no_change counts partition total metrics."""
        total = regression + improvement + no_change
        summary = make_outcome_summary(
            regression_count=regression,
            improvement_count=improvement,
            no_change_count=no_change,
        )
        assert summary.regression_count + summary.improvement_count + summary.no_change_count == total


# ── JSON round-trip property ─────────────────────────────────────────

@pytest.mark.property
class TestJsonRoundTrip:

    @given(
        step=st.integers(min_value=0, max_value=10000),
        severity=st_severity,
        event_type=st_event_type,
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_event_roundtrip(self, step: int, severity: str, event_type: str, score: float) -> None:
        evt = Event(id=f"evt-{step}", type=event_type, step=step, severity=severity, score=score)
        restored = Event.model_validate_json(evt.model_dump_json())
        assert restored == evt

    @given(
        idx=st.integers(min_value=0, max_value=100),
        progress=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        reward=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_episode_record_roundtrip(self, idx: int, progress: float, reward: float) -> None:
        rec = EpisodeRecord(episode_idx=idx, final_track_progress=progress, total_reward=reward)
        restored = EpisodeRecord.model_validate_json(rec.model_dump_json())
        assert restored == rec

    def test_metric_comparison_roundtrip(self) -> None:
        mc = make_metric_comparison()
        restored = MetricComparison.model_validate_json(mc.model_dump_json())
        assert restored == mc

    def test_outcome_summary_roundtrip(self) -> None:
        summary = make_outcome_summary()
        restored = OutcomeSummary.model_validate_json(summary.model_dump_json())
        assert restored == summary
