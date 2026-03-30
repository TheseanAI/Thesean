"""Tests for F1 signal translator completeness — INV-2-*."""

from __future__ import annotations

import numpy as np
import pytest

from thesean.adapters.f1.signals import F1SignalTranslator


@pytest.mark.unit
class TestTranslateStepCompleteness:
    """INV-2-6: translate_step() always returns exactly 13 keys."""

    def setup_method(self) -> None:
        self.translator = F1SignalTranslator()

    def test_full_step_returns_13_keys(self) -> None:
        step = {
            "obs": {"aux": np.zeros(16)},
            "action": np.array([0.1, 0.5, 0.0]),
            "reward": 0.5,
            "done": False,
            "info": {"offtrack_steps": 0},
            "car_state": {"velocity": 20.0, "theta": 0.1},
            "track_progress": 0.3,
        }
        signals = self.translator.translate_step(step)
        assert len(signals) == 13

    def test_empty_step_returns_13_keys(self) -> None:
        signals = self.translator.translate_step({})
        assert len(signals) == 13

    def test_partial_step_returns_13_keys(self) -> None:
        step = {"action": np.array([0.2, 0.3, 0.1])}
        signals = self.translator.translate_step(step)
        assert len(signals) == 13

    def test_missing_fields_default_to_zero(self) -> None:
        """Missing fields should produce 0.0, not NaN."""
        signals = self.translator.translate_step({})
        for name, value in signals.items():
            assert not np.isnan(value), f"Signal {name} is NaN for empty step"
            assert value == 0.0, f"Signal {name} should be 0.0 for empty step, got {value}"

    def test_signal_names_match_translate_keys(self) -> None:
        """translate_step() keys match signal_names()."""
        names = set(self.translator.signal_names())
        keys = set(self.translator.translate_step({}))
        assert names == keys


@pytest.mark.unit
class TestSignalSchemaThresholds:
    """INV-2-7: signal_schema() thresholds all >= 0.0."""

    def setup_method(self) -> None:
        self.translator = F1SignalTranslator()

    def test_all_thresholds_non_negative(self) -> None:
        schema = self.translator.signal_schema()
        for group_name in schema.group_order:
            for signal_def in schema.groups[group_name]:
                assert signal_def.delta_threshold >= 0.0, (
                    f"Threshold for {signal_def.name} is negative: {signal_def.delta_threshold}"
                )

    def test_schema_covers_all_signals(self) -> None:
        schema = self.translator.signal_schema()
        schema_names = set(schema.signal_names())
        translator_names = set(self.translator.signal_names())
        assert schema_names == translator_names
