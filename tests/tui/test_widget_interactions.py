"""Widget pilot tests — mount individual widgets in a shell app and drive them."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from thesean.models.event import Event
from thesean.tui.widgets.event_navigator import EventNavigator
from thesean.tui.widgets.transport_bar import TransportBar
from thesean.tui.widgets.verdict_strip import VerdictStrip

pytestmark = [pytest.mark.asyncio, pytest.mark.tui]


# ── TransportBar ──


class TransportApp(App):
    def compose(self) -> ComposeResult:
        yield TransportBar()


async def test_transport_step_forward():
    app = TransportApp()
    async with app.run_test() as _pilot:
        bar = app.query_one(TransportBar)
        bar.max_step = 100
        bar.current_step = 50
        bar.step_forward()
        assert bar.current_step == 51


async def test_transport_step_backward():
    app = TransportApp()
    async with app.run_test() as _pilot:
        bar = app.query_one(TransportBar)
        bar.max_step = 100
        bar.current_step = 50
        bar.step_backward(10)
        assert bar.current_step == 40


async def test_transport_step_clamp_lower():
    app = TransportApp()
    async with app.run_test() as _pilot:
        bar = app.query_one(TransportBar)
        bar.max_step = 100
        bar.current_step = 2
        bar.step_backward(10)
        assert bar.current_step == 0


async def test_transport_step_clamp_upper():
    app = TransportApp()
    async with app.run_test() as _pilot:
        bar = app.query_one(TransportBar)
        bar.max_step = 100
        bar.current_step = 98
        bar.step_forward(10)
        assert bar.current_step == 100


async def test_transport_goto_step():
    app = TransportApp()
    async with app.run_test() as _pilot:
        bar = app.query_one(TransportBar)
        bar.max_step = 50
        bar.goto_step(25)
        assert bar.current_step == 25
        bar.goto_step(999)
        assert bar.current_step == 50


# ── EventNavigator ──


class EventNavApp(App):
    def compose(self) -> ComposeResult:
        yield EventNavigator()


def _make_events(n: int) -> list[Event]:
    from tests.tui.widgets.conftest import make_events
    return make_events(n)


async def test_event_navigator_set_events():
    app = EventNavApp()
    async with app.run_test() as pilot:
        nav = app.query_one(EventNavigator)
        events = _make_events(3)
        nav.set_events(events)
        await pilot.pause()
        assert nav._events == events
        assert len(nav._item_widgets) == 3


async def test_event_navigator_highlight():
    app = EventNavApp()
    async with app.run_test() as pilot:
        nav = app.query_one(EventNavigator)
        events = _make_events(3)
        nav.set_events(events)
        await pilot.pause()

        nav.highlight(1)
        assert nav._highlighted_idx == 1
        # The highlighted widget should have the selected class
        for item_idx, widget in nav._item_widgets:
            if item_idx == 1:
                assert "en-item-selected" in widget.classes


async def test_event_navigator_empty():
    app = EventNavApp()
    async with app.run_test() as pilot:
        nav = app.query_one(EventNavigator)
        nav.set_events([])
        await pilot.pause()
        assert nav._events == []
        assert len(nav._item_widgets) == 0


# ── VerdictStrip ──


class VerdictApp(App):
    def compose(self) -> ComposeResult:
        yield VerdictStrip()


async def test_verdict_strip_awaiting():
    app = VerdictApp()
    async with app.run_test() as _pilot:
        strip = app.query_one(VerdictStrip)
        strip.set_awaiting()
        assert "vs-awaiting" in strip.classes


async def test_verdict_strip_running():
    app = VerdictApp()
    async with app.run_test() as _pilot:
        strip = app.query_one(VerdictStrip)
        strip.set_running()
        assert "vs-running" in strip.classes


async def test_verdict_strip_verdict():
    from thesean.models.episode import OutcomeSummary

    outcomes = OutcomeSummary(
        verdict="regression",
        primary_metric="final_track_progress",
        primary_metric_display="completion",
        baseline_value=0.8,
        candidate_value=0.6,
        delta_pct=-25.0,
        significant=True,
        regression_count=1,
        improvement_count=0,
        no_change_count=0,
        verdict_headline="Candidate underperformed.",
        primary_metric_line="completion: 60% vs 80% (-25.0%)",
        findings_count_line="1 metric regressed",
    )

    app = VerdictApp()
    async with app.run_test() as _pilot:
        strip = app.query_one(VerdictStrip)
        strip.set_verdict(outcomes)
        assert "vs-verdict-regression" in strip.classes


async def test_verdict_strip_state_cycle():
    """Verify classes change as the strip cycles through states."""
    app = VerdictApp()
    async with app.run_test() as _pilot:
        strip = app.query_one(VerdictStrip)

        strip.set_awaiting()
        assert "vs-awaiting" in strip.classes
        assert "vs-running" not in strip.classes

        strip.set_running()
        assert "vs-running" in strip.classes
        assert "vs-awaiting" not in strip.classes

        strip.set_pending()
        assert "vs-pending" in strip.classes
        assert "vs-running" not in strip.classes
