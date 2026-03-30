"""Tests for TransportBar — step bounds."""

from __future__ import annotations

import pytest

from thesean.tui.widgets.transport_bar import TransportBar


@pytest.mark.unit
class TestTransportBarStepBounds:

    def test_step_forward_clamped_to_max(self) -> None:
        """Cannot go above max_step."""
        bar = TransportBar()
        bar.max_step = 10
        bar.current_step = 10
        # step_forward posts message only if value changes
        bar.step_forward()
        assert bar.current_step == 10

    def test_step_backward_clamped_to_zero(self) -> None:
        """Cannot go below 0."""
        bar = TransportBar()
        bar.max_step = 10
        bar.current_step = 0
        bar.step_backward()
        assert bar.current_step == 0

    def test_goto_step_clamps_high(self) -> None:
        bar = TransportBar()
        bar.max_step = 5
        bar.current_step = 0
        bar.goto_step(100)
        assert bar.current_step == 5

    def test_goto_step_clamps_low(self) -> None:
        bar = TransportBar()
        bar.max_step = 5
        bar.current_step = 3
        bar.goto_step(-10)
        assert bar.current_step == 0
