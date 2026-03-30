"""Tests for Phase 2: Event detection engine."""

from __future__ import annotations

import pytest

from thesean.pipeline.events.config import EventDetectionConfig
from thesean.pipeline.events.detection import detect_events
from thesean.pipeline.events.divergence import (
    compute_divergence_score,
    compute_step_deltas,
    extract_step_signals,
    find_persistent_onset,
)

# ── Helpers ──────────────────────────────────────────────────────────────

def _make_step(
    action=(0.0, 0.5, 0.0),
    car_state=None,
    track_progress=0.5,
    reward=0.1,
    done=False,
    info=None,
):
    """Build a synthetic step dict matching F1 data format."""
    if car_state is None:
        car_state = {"x": 0.0, "y": 0.0, "theta": 0.0, "velocity": 10.0}
    return {
        "action": list(action),
        "car_state": car_state,
        "track_progress": track_progress,
        "reward": reward,
        "done": done,
        "info": info or {},
    }


def _make_episode(steps):
    return {"steps": steps}


# ── extract_step_signals ─────────────────────────────────────────────────

class TestExtractStepSignals:
    def test_extracts_action(self):
        s = extract_step_signals({"action": [0.3, 0.7, 0.1]})
        assert s["steering"] == pytest.approx(0.3)
        assert s["throttle"] == pytest.approx(0.7)
        assert s["brake"] == pytest.approx(0.1)

    def test_extracts_car_state(self):
        s = extract_step_signals({"car_state": {"x": 1.0, "theta": 0.5, "velocity": 20.0}})
        assert s["x"] == pytest.approx(1.0)
        assert s["theta"] == pytest.approx(0.5)
        assert s["velocity"] == pytest.approx(20.0)

    def test_handles_empty_step(self):
        s = extract_step_signals({})
        assert s == {}

    def test_extracts_progress_and_reward(self):
        s = extract_step_signals({"track_progress": 0.75, "reward": 0.02})
        assert s["progress"] == pytest.approx(0.75)
        assert s["reward"] == pytest.approx(0.02)


# ── compute_step_deltas ─────────────────────────────────────────────────

class TestComputeStepDeltas:
    def test_matching_keys(self):
        a = {"steering": 0.1, "throttle": 0.5}
        b = {"steering": 0.4, "throttle": 0.5}
        d = compute_step_deltas(a, b)
        assert d["steering_delta"] == pytest.approx(0.3)
        assert d["throttle_delta"] == pytest.approx(0.0)

    def test_disjoint_keys(self):
        d = compute_step_deltas({"x": 1.0}, {"y": 2.0})
        assert d == {}


# ── compute_divergence_score ─────────────────────────────────────────────

class TestComputeDivergenceScore:
    def test_zero_deltas(self):
        config = EventDetectionConfig()
        score = compute_divergence_score({}, config)
        assert score == 0.0

    def test_nonzero(self):
        config = EventDetectionConfig(signal_weights={"a_delta": 1.0}, active_signals=["a_delta"])
        score = compute_divergence_score({"a_delta": 0.5}, config)
        assert score == pytest.approx(0.5)


# ── find_persistent_onset ────────────────────────────────────────────────

class TestFindPersistentOnset:
    def test_finds_onset(self):
        scores = [0.0, 0.0, 0.3, 0.3, 0.3, 0.3, 0.0]
        assert find_persistent_onset(scores, threshold=0.2, persistence_k=4) == 2

    def test_no_persistent_run(self):
        scores = [0.0, 0.3, 0.3, 0.0, 0.3, 0.0]
        assert find_persistent_onset(scores, threshold=0.2, persistence_k=4) is None

    def test_onset_at_start(self):
        scores = [0.5, 0.5, 0.5, 0.5, 0.0]
        assert find_persistent_onset(scores, threshold=0.2, persistence_k=4) == 0

    def test_below_threshold(self):
        scores = [0.1, 0.1, 0.1, 0.1]
        assert find_persistent_onset(scores, threshold=0.2, persistence_k=2) is None


# ── detect_events (integration) ─────────────────────────────────────────

class TestDetectEvents:
    def test_empty_episodes(self):
        assert detect_events([], []) == []

    def test_identical_episodes_no_divergence(self):
        steps = [_make_step() for _ in range(20)]
        ep = [_make_episode(steps)]
        events = detect_events(ep, ep, EventDetectionConfig(threshold=0.1, persistence_k=2))
        # Should get max_metric_gap with score=0 (no divergence) — filtered by score > 0
        signal_events = [e for e in events if e.type == "first_signal_divergence"]
        assert len(signal_events) == 0

    def test_detects_divergence_at_known_step(self):
        """Baseline holds steady, candidate diverges at step 10."""
        baseline_steps = [_make_step(action=(0.0, 0.5, 0.0)) for _ in range(30)]
        candidate_steps = []
        for t in range(30):
            if t < 10:
                candidate_steps.append(_make_step(action=(0.0, 0.5, 0.0)))
            else:
                # Large steering divergence
                candidate_steps.append(_make_step(action=(0.8, 0.5, 0.0)))

        config = EventDetectionConfig(
            threshold=0.05,
            persistence_k=3,
            signal_weights={"steering_delta": 1.0},
            active_signals=["steering_delta"],
            action_threshold=0.3,
        )
        events = detect_events(
            [_make_episode(baseline_steps)],
            [_make_episode(candidate_steps)],
            config,
        )
        # Should detect first_signal_divergence at step 10
        signal_events = [e for e in events if e.type == "first_signal_divergence"]
        assert len(signal_events) == 1
        assert signal_events[0].step == 10

        # Should also detect action divergence
        action_events = [e for e in events if e.type == "first_action_divergence"]
        assert len(action_events) == 1
        assert action_events[0].step == 10

    def test_detects_terminal_event(self):
        """Candidate terminates early while baseline continues."""
        baseline_steps = [_make_step() for _ in range(20)]
        candidate_steps = [_make_step() for _ in range(15)]
        candidate_steps.append(_make_step(done=True, info={"termination": "off_track"}))

        events = detect_events(
            [_make_episode(baseline_steps)],
            [_make_episode(candidate_steps)],
        )
        terminal_events = [e for e in events if e.type == "terminal"]
        assert len(terminal_events) == 1
        assert terminal_events[0].step == 15
        assert terminal_events[0].metadata["reason"] == "off_track"

    def test_detects_risk_spike(self):
        """Candidate offtrack risk spikes."""
        baseline_steps = [_make_step(info={"offtrack_steps": 0}) for _ in range(20)]
        candidate_steps = []
        for t in range(20):
            risk = 0 if t < 12 else 5
            candidate_steps.append(_make_step(info={"offtrack_steps": risk}))

        config = EventDetectionConfig(risk_threshold=3.0)
        events = detect_events(
            [_make_episode(baseline_steps)],
            [_make_episode(candidate_steps)],
            config,
        )
        risk_events = [e for e in events if e.type == "first_risk_spike"]
        assert len(risk_events) == 1
        assert risk_events[0].step == 12

    def test_max_metric_gap(self):
        """Always emits max_metric_gap when there's any divergence."""
        baseline_steps = [_make_step(action=(0.0, 0.5, 0.0)) for _ in range(10)]
        candidate_steps = [_make_step(action=(0.1, 0.5, 0.0)) for _ in range(10)]

        config = EventDetectionConfig(
            threshold=999.0,  # Very high — no persistent divergence
            persistence_k=2,
        )
        events = detect_events(
            [_make_episode(baseline_steps)],
            [_make_episode(candidate_steps)],
            config,
        )
        gap_events = [e for e in events if e.type == "max_metric_gap"]
        assert len(gap_events) == 1

    def test_events_sorted_by_step(self):
        """Events should be sorted by step."""
        baseline_steps = [_make_step(action=(0.0, 0.5, 0.0), info={"offtrack_steps": 0}) for _ in range(30)]
        candidate_steps = []
        for t in range(30):
            if t < 15:
                candidate_steps.append(_make_step(action=(0.0, 0.5, 0.0), info={"offtrack_steps": 0}))
            else:
                candidate_steps.append(_make_step(
                    action=(0.9, 0.5, 0.0),
                    info={"offtrack_steps": 5},
                ))

        events = detect_events(
            [_make_episode(baseline_steps)],
            [_make_episode(candidate_steps)],
        )
        steps = [e.step for e in events]
        assert steps == sorted(steps)
