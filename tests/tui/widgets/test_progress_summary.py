"""Unit tests for ProgressSummary pure helper functions."""

from __future__ import annotations

from thesean.adapters.f1.signals import (
    _segment_curvature_bucket,
    _segment_turn_direction,
    _unwrap_heading_window,
)
from thesean.tui.widgets.progress_summary import (
    _event_progress,
    _progress_to_col,
)


def _make_event(step: int, severity: str = "warning") -> "Event":  # noqa: F821
    """Create a minimal Event for testing."""
    from thesean.models.event import Event

    return Event(id=f"evt-{step}", type="first_divergence", step=step, severity=severity)


class TestProgressPositionMapping:
    def test_zero_maps_to_first_col(self) -> None:
        assert _progress_to_col(0.0, 40) == 0

    def test_one_maps_to_last_col(self) -> None:
        assert _progress_to_col(1.0, 40) == 39

    def test_half_maps_to_middle(self) -> None:
        col = _progress_to_col(0.5, 41)
        assert col == 20

    def test_clamps_negative(self) -> None:
        assert _progress_to_col(-0.5, 40) == 0

    def test_clamps_above_one(self) -> None:
        assert _progress_to_col(1.5, 40) == 39

    def test_zero_width(self) -> None:
        assert _progress_to_col(0.5, 0) == 0


class TestSegmentTurnAndCurvature:
    def test_constant_heading_is_straight(self) -> None:
        headings = [1.0] * 10
        unwrapped = _unwrap_heading_window(headings)
        deltas = [unwrapped[i] - unwrapped[i - 1] for i in range(1, len(unwrapped))]
        direction, mean_delta = _segment_turn_direction(deltas)
        assert direction == "straight"
        assert abs(mean_delta) < 1e-9

        bucket, val = _segment_curvature_bucket(unwrapped)
        assert bucket == "straight"

    def test_steadily_increasing_heading_is_left(self) -> None:
        # Steady left turn: heading increases by 0.03/step
        headings = [i * 0.03 for i in range(11)]
        unwrapped = _unwrap_heading_window(headings)
        deltas = [unwrapped[i] - unwrapped[i - 1] for i in range(1, len(unwrapped))]
        direction, mean_delta = _segment_turn_direction(deltas)
        assert direction == "left"
        assert mean_delta > 0

    def test_steadily_decreasing_heading_is_right(self) -> None:
        headings = [-i * 0.03 for i in range(11)]
        unwrapped = _unwrap_heading_window(headings)
        deltas = [unwrapped[i] - unwrapped[i - 1] for i in range(1, len(unwrapped))]
        direction, _ = _segment_turn_direction(deltas)
        assert direction == "right"

    def test_heading_wrap_no_false_spike(self) -> None:
        """Heading crossing ±π boundary should unwrap smoothly."""
        # Heading going from ~π to ~-π (wrapping around)
        headings = [3.0, 3.05, 3.1, 3.14, -3.13, -3.08, -3.03]
        unwrapped = _unwrap_heading_window(headings)
        deltas = [unwrapped[i] - unwrapped[i - 1] for i in range(1, len(unwrapped))]
        # All deltas should be small (no giant jump)
        for d in deltas:
            assert abs(d) < 0.2, f"False spike detected: delta={d}"
        # Direction should be left (increasing through wrap)
        direction, _ = _segment_turn_direction(deltas)
        assert direction == "left"

    def test_curvature_gentle(self) -> None:
        # Gentle curve: heading increases at constant rate (zero second diff ideally,
        # but floating point gives near-zero)
        headings = [i * 0.01 for i in range(11)]
        _, val = _segment_curvature_bucket(headings)
        # Constant rate → second diff ≈ 0 → straight
        assert val < 0.005

    def test_curvature_sharp(self) -> None:
        # Sharp: accelerating heading change
        headings = [i * i * 0.05 for i in range(11)]
        bucket, _ = _segment_curvature_bucket(headings)
        assert bucket in ("moderate", "sharp")


class TestEventProgressPairAware:
    def test_uses_average_of_both_sides(self) -> None:
        evt = _make_event(step=10)
        signals_a = {10: {"lap_progress": 0.4}}
        signals_b = {10: {"lap_progress": 0.6}}
        prog = _event_progress(evt, signals_a, signals_b, max_step=100)
        assert abs(prog - 0.5) < 1e-9

    def test_fallback_to_single_side_a(self) -> None:
        evt = _make_event(step=10)
        signals_a = {10: {"lap_progress": 0.3}}
        signals_b: dict = {}
        prog = _event_progress(evt, signals_a, signals_b, max_step=100)
        assert abs(prog - 0.3) < 1e-9

    def test_fallback_to_single_side_b(self) -> None:
        evt = _make_event(step=10)
        signals_a: dict = {}
        signals_b = {10: {"lap_progress": 0.7}}
        prog = _event_progress(evt, signals_a, signals_b, max_step=100)
        assert abs(prog - 0.7) < 1e-9

    def test_fallback_to_step_ratio(self) -> None:
        evt = _make_event(step=50)
        prog = _event_progress(evt, {}, {}, max_step=100)
        assert abs(prog - 0.5) < 1e-9

    def test_fallback_zero_max_step(self) -> None:
        evt = _make_event(step=0)
        prog = _event_progress(evt, {}, {}, max_step=0)
        assert prog == 0.0
