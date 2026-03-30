"""Signal timeline — character-based sparkline with event markers."""

from __future__ import annotations

from enum import Enum

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive, var
from textual.widgets import Static

from thesean.models.event import Event

# Unicode block sparkline characters (proper visual bars)
_SPARK_CHARS = " ▁▂▃▄▅▆▇█"


class TimelineMode(str, Enum):
    """Display modes for the signal timeline."""

    DIVERGENCE = "divergence"
    SIGNAL_COMPARE = "signal_compare"


def _sparkline(values: list[float], width: int) -> str:
    """Render a sparkline from values into a fixed-width string."""
    if not values:
        return " " * width

    mn = min(values)
    mx = max(values)
    rng = mx - mn if mx != mn else 1.0

    # Downsample or upsample to fit width
    result = []
    for i in range(width):
        idx = int(i * len(values) / width)
        idx = min(idx, len(values) - 1)
        normalized = (values[idx] - mn) / rng
        char_idx = int(normalized * (len(_SPARK_CHARS) - 1))
        result.append(_SPARK_CHARS[char_idx])
    return "".join(result)


def _event_markers(events: list[Event], max_step: int, width: int) -> str:
    """Render event position markers aligned to sparkline width."""
    if not events or max_step == 0:
        return "─" * width
    chars = ["─"] * width
    for evt in events:
        pos = int(evt.step * width / max_step)
        pos = min(pos, width - 1)
        if evt.severity == "critical":
            chars[pos] = "●"
        elif evt.severity == "warning":
            chars[pos] = "◆"
        else:
            chars[pos] = "·"
    return "".join(chars)


class SignalTimeline(Vertical):
    """Character-based timeline showing divergence score over time."""

    current_step: reactive[int] = reactive(0)
    timeline_mode: var[TimelineMode] = var(TimelineMode.DIVERGENCE)

    DEFAULT_CSS = """
    SignalTimeline {
        height: auto;
        max-height: 10;
        border: round $panel;
        padding: 1 2;
    }
    SignalTimeline .st-sparkline {
        color: $accent;
    }
    SignalTimeline .st-events {
        color: $error;
    }
    SignalTimeline .st-cursor {
        color: $warning;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._scores: list[float] = []
        self._events: list[Event] = []
        self._max_step: int = 0
        self._active_signal_name: str = ""
        self._values_a: list[float] = []
        self._values_b: list[float] = []
        self._window_range: tuple[int, int] | None = None

    def compose(self) -> ComposeResult:
        self.border_title = "Timeline"
        yield Static("", id="st-spark-a", classes="st-sparkline")
        yield Static("", id="st-spark-b", classes="st-sparkline")
        yield Static("", id="st-event-markers", classes="st-events")
        yield Static("", id="st-cursor-line", classes="st-cursor")

    def set_data(
        self,
        scores: list[float],
        events: list[Event],
        max_step: int,
        values_a: list[float] | None = None,
        values_b: list[float] | None = None,
        active_signal_name: str = "",
        window_range: tuple[int, int] | None = None,
    ) -> None:
        self._scores = scores
        self._events = events
        self._max_step = max_step
        self._values_a = values_a or []
        self._values_b = values_b or []
        self._active_signal_name = active_signal_name
        self._window_range = window_range
        self._refresh_display()

    def cycle_mode(self) -> None:
        """Toggle between divergence and signal_compare modes."""
        if self.timeline_mode == TimelineMode.DIVERGENCE:
            self.timeline_mode = TimelineMode.SIGNAL_COMPARE
        else:
            self.timeline_mode = TimelineMode.DIVERGENCE

    def watch_timeline_mode(self, value: TimelineMode) -> None:
        self._refresh_display()

    def watch_current_step(self, step: int) -> None:
        self._render_cursor(step)

    def _refresh_display(self) -> None:
        width = max(self.size.width - 4, 20) if self.size.width > 0 else 60

        # Update border title with mode label
        spark_a = self.query_one("#st-spark-a", Static)
        spark_b = self.query_one("#st-spark-b", Static)

        if self.timeline_mode == TimelineMode.DIVERGENCE:
            # Single sparkline from divergence scores
            title_parts = ["Timeline"]
            title_parts.append("[divergence]")
            if self._active_signal_name:
                title_parts.append(self._active_signal_name)
            if self._window_range:
                lo, hi = self._window_range
                title_parts.append(f"[{lo}..{hi}]")
            self.border_title = " \u2014 ".join(title_parts)
            spark_text = Text()
            spark_text.append("S ", style="bold dim")
            spark_text.append(_sparkline(self._scores, width), style="")
            spark_a.update(spark_text)
            spark_b.update("")
        else:
            # Dual sparklines A/B (signal_compare mode)
            signal_label = self._active_signal_name or "signal"
            title_parts = ["Timeline", f"[{signal_label}]"]
            if self._window_range:
                lo, hi = self._window_range
                title_parts.append(f"[{lo}..{hi}]")
            self.border_title = " \u2014 ".join(title_parts)
            if self._values_a:
                text_a = Text()
                text_a.append("A ", style="bold dim")
                text_a.append(_sparkline(self._values_a, width), style="")
                spark_a.update(text_a)
            else:
                text_a = Text()
                text_a.append("S ", style="bold dim")
                text_a.append(_sparkline(self._scores, width), style="")
                spark_a.update(text_a)
            if self._values_b:
                text_b = Text()
                text_b.append("B ", style="bold dim")
                text_b.append(_sparkline(self._values_b, width), style="")
                spark_b.update(text_b)
            else:
                spark_b.update("")

        # Event markers
        markers = self.query_one("#st-event-markers", Static)
        marker_text = Text()
        marker_text.append("E ", style="bold dim")
        marker_text.append(_event_markers(self._events, self._max_step, width), style="")
        markers.update(marker_text)

        self._render_cursor(self.current_step)

    def _render_cursor(self, step: int) -> None:
        width = max(self.size.width - 4, 20) if self.size.width > 0 else 60
        cursor = self.query_one("#st-cursor-line", Static)
        if self._max_step > 0:
            pos = int(step * width / self._max_step)
            pos = min(pos, width - 1)
            line = "╌" * pos + "▼" + "╌" * (width - pos - 1)
            cursor_text = Text()
            cursor_text.append("  ", style="")
            cursor_text.append(line, style="")
            cursor_text.append(f" t={step}", style="bold")
            cursor.update(cursor_text)
        else:
            cursor.update("")
