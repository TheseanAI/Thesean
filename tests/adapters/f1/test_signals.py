"""Tests for Phase 3: F1 signal translator."""

from __future__ import annotations

import pytest

from thesean.adapters.f1.signals import F1SignalTranslator


class TestF1SignalTranslator:
    def setup_method(self):
        self.translator = F1SignalTranslator()

    def test_signal_names(self):
        names = self.translator.signal_names()
        assert "steering" in names
        assert "speed" in names
        assert "lidar_min" in names
        assert len(names) > 0

    def test_translate_full_step(self):
        step = {
            "action": [0.3, 0.7, 0.1],
            "car_state": {"x": 10.0, "y": 5.0, "theta": 1.2, "velocity": 30.0},
            "track_progress": 0.6,
            "reward": 0.02,
            "info": {"offtrack_steps": 2},
            "obs": {"aux": [0.0] + [0.5] * 15},  # aux[0]=speed, aux[1:16]=lidar
        }
        signals = self.translator.translate_step(step)
        assert signals["steering"] == pytest.approx(0.3)
        assert signals["throttle"] == pytest.approx(0.7)
        assert signals["brake"] == pytest.approx(0.1)
        assert signals["heading"] == pytest.approx(1.2)
        assert signals["speed"] == pytest.approx(30.0)
        assert signals["lap_progress"] == pytest.approx(0.6)
        assert signals["lidar_min"] == pytest.approx(0.5)
        assert signals["offtrack_risk"] == pytest.approx(2.0)
        assert signals["reward"] == pytest.approx(0.02)

    def test_translate_empty_step(self):
        signals = self.translator.translate_step({})
        # Always returns all 13 keys with 0.0 defaults
        assert len(signals) == 13
        assert all(v == 0.0 for v in signals.values())

    def test_translate_partial_step(self):
        step = {"action": [0.5, 0.5, 0.0]}
        signals = self.translator.translate_step(step)
        assert signals["steering"] == pytest.approx(0.5)
        # Missing fields default to 0.0
        assert signals["speed"] == 0.0
        assert len(signals) == 13
