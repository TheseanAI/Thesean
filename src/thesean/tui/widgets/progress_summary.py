"""Progress summary — track position, signal comparison, and segment analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

if TYPE_CHECKING:
    from thesean.core.signal_schema import SignalSchema

from thesean.models.event import Event

# ── Pure helper functions (testable independently) ──


def _progress_to_col(progress: float, width: int) -> int:
    """Map a 0.0–1.0 progress value to a column index."""
    if width <= 0:
        return 0
    progress = max(0.0, min(1.0, progress))
    return int(progress * (width - 1))


def _event_progress(
    event: Event,
    signals_a: dict[int, dict[str, float]],
    signals_b: dict[int, dict[str, float]],
    max_step: int,
    progress_key: str = "lap_progress",
) -> float:
    """Compute event position as progress 0.0–1.0, pair-aware."""
    step = event.step
    prog_a = signals_a.get(step, {}).get(progress_key) if signals_a else None
    prog_b = signals_b.get(step, {}).get(progress_key) if signals_b else None

    if prog_a is not None and prog_b is not None:
        return (prog_a + prog_b) / 2.0
    if prog_a is not None:
        return prog_a
    if prog_b is not None:
        return prog_b
    if max_step > 0:
        return step / max_step
    return 0.0


# Block characters for progress bars
_BAR_FULL = "\u2588"  # █
_BAR_EMPTY = "\u2591"  # ░


def _render_bar(value: float, width: int) -> str:
    """Render a horizontal bar for 0.0–1.0 value."""
    filled = int(value * width)
    return _BAR_FULL * filled + _BAR_EMPTY * (width - filled)


# ── Widget ──


class ProgressSummary(Vertical):
    """Track position + signal comparison + segment analysis for investigation."""

    DEFAULT_CSS = """
    ProgressSummary {
        height: 1fr;
        border: round $panel;
        padding: 1 2;
    }
    ProgressSummary .ps-content {
        color: $text-muted;
    }
    """

    def __init__(self, track_geometry: list[tuple[float, float]] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._raster: BrailleTrackRaster | None = None
        if track_geometry:
            from thesean.tui.widgets.track_map import BrailleTrackRaster
            self._raster = BrailleTrackRaster(track_geometry)
        self._signals_a: dict[int, dict[str, float]] = {}
        self._signals_b: dict[int, dict[str, float]] = {}
        self._events: list[Event] = []
        self._max_step: int = 0
        self._current_step: int = 0
        self._schema: SignalSchema | None = None
        self._translator: Any = None
        self._progress_key: str = "lap_progress"
        self._focus_deltas: list[tuple[str, float]] = []

    def compose(self) -> ComposeResult:
        self.border_title = "Track Progress"
        yield Static("No episode data \u2014 run evaluation to begin", id="ps-content", classes="ps-content")

    def set_schema(self, schema: SignalSchema | None, translator: Any = None) -> None:
        self._schema = schema
        self._translator = translator
        self._progress_key = "lap_progress"
        if schema:
            for name in schema.signal_names():
                if "progress" in name:
                    self._progress_key = name
                    break

    def set_data(
        self,
        signals_a: dict[int, dict[str, float]],
        signals_b: dict[int, dict[str, float]],
        events: list[Event],
        max_step: int,
    ) -> None:
        """Called on mount and episode change. Stores full signal dicts."""
        self._signals_a = signals_a or {}
        self._signals_b = signals_b or {}
        self._events = events or []
        self._max_step = max_step
        if not self._signals_a and not self._signals_b:
            self.query_one("#ps-content", Static).update(
                "No episode data \u2014 run evaluation to begin"
            )
        else:
            step0 = min(self._signals_a.keys()) if self._signals_a else 0
            sa = self._signals_a.get(step0)
            sb = self._signals_b.get(step0)
            self.update_step(step0, sa, sb)

    def set_focus_signals(self, deltas: list[tuple[str, float]]) -> None:
        """Store signal deltas to render as focus section."""
        self._focus_deltas = deltas

    def update_step(
        self,
        step: int,
        sa: dict[str, float] | None,
        sb: dict[str, float] | None,
    ) -> None:
        """Called on every step change. Re-renders all sections."""
        from rich.console import Group
        
        self._current_step = step

        pos_text = self._render_position(step, sa, sb)
        evt_text = self._render_event_rail()
        seg_group = self._render_segment(step, sa, sb)
        foc_text = self._render_focus()

        self.query_one("#ps-content", Static).update(Group(pos_text, evt_text, seg_group, foc_text))

    # ── Section: Position ──

    def _render_position(
        self,
        step: int,
        sa: dict[str, float] | None,
        sb: dict[str, float] | None,
    ) -> Text:
        text = Text()
        pk = self._progress_key
        prog_a = sa.get(pk) if sa else None
        prog_b = sb.get(pk) if sb else None
        bar_width = max(16, min(self.size.width - 20, 40))

        if prog_a is not None:
            text.append("  A  ", style="bold")
            if self._raster:
                text.append_text(self._raster.render(prog_a, color="cyan", dim_color="grey37"))
                text.append(f"  {prog_a:.3f}\n")
            else:
                bar_a = _render_bar(prog_a, bar_width)
                text.append(bar_a, style="cyan")
                text.append(f"  {prog_a:.3f}\n")
        else:
            text.append("  A  ", style="bold")
            text.append("no data\n", style="dim")

        if prog_b is not None:
            text.append("  B  ", style="bold")
            if self._raster:
                text.append_text(self._raster.render(prog_b, color="magenta", dim_color="grey37"))
                text.append(f"  {prog_b:.3f}\n")
            else:
                bar_b = _render_bar(prog_b, bar_width)
                text.append(bar_b, style="magenta")
                text.append(f"  {prog_b:.3f}\n")
        else:
            text.append("  B  ", style="bold")
            text.append("no data\n", style="dim")

        # Delta
        if prog_a is not None and prog_b is not None:
            delta = prog_b - prog_a
            sign = "+" if delta >= 0 else ""
            delta_style = "green" if delta > 0.01 else ("red" if delta < -0.01 else "dim")
            text.append("       ")
            text.append(f"\u0394 = {sign}{delta:.3f}", style=delta_style)
            text.append("\n")

        text.append("\n")
        return text

    # ── Section: Event Rail ──

    def _render_event_rail(self) -> Text:
        text = Text()
        if not self._events:
            return text

        strip_width = max(20, min(self.size.width - 12, 60))
        pk = self._progress_key

        rail = ["\u2500"] * strip_width
        rail[0] = "S"
        rail[-1] = "F"

        _SEV_RANK = {"critical": 2, "warning": 1, "info": 0}
        _SEV_CHAR = {"critical": "\u25cf", "warning": "\u25c6", "info": "\u00b7"}
        col_severity: dict[int, int] = {}

        for evt in self._events:
            prog = _event_progress(evt, self._signals_a, self._signals_b, self._max_step, pk)
            col = _progress_to_col(prog, strip_width)
            sev = _SEV_RANK.get(evt.severity, 0)
            if col in col_severity and col_severity[col] >= sev:
                continue
            col_severity[col] = sev
            rail[col] = _SEV_CHAR.get(evt.severity, "\u00b7")

        text.append("  Events ", style="dim bold")
        text.append("".join(rail), style="dim")
        text.append("\n\n")
        return text

    # ── Section: Segment Summary ──

    def _render_segment(
        self,
        step: int,
        sa: dict[str, float] | None,
        sb: dict[str, float] | None,
    ) -> Any:
        from rich.console import Group
        from rich.table import Table
        
        window_half = 5
        lo = max(0, step - window_half)
        hi = min(self._max_step, step + window_half)

        header = Text()
        header.append("  Segment ", style="dim bold")
        header.append(f"step {step}", style="bold")
        header.append(f"  window {lo}\u2013{hi}", style="dim")

        table = Table(box=None, show_header=False, padding=(0, 2, 0, 4))
        table.add_column("Metric", style="dim")
        table.add_column("Values")

        if self._translator and hasattr(self._translator, "analyze_segment"):
            lines = self._translator.analyze_segment(
                self._signals_a, self._signals_b, step, window_half=window_half
            )
            for label, value in lines:
                table.add_row(label, value)
        elif sa and sb:
            # Top divergent signals at current step
            deltas = [(k, sa.get(k, 0.0), sb.get(k, 0.0), abs(sa.get(k, 0) - sb.get(k, 0)))
                      for k in set(sa) & set(sb)]
            deltas.sort(key=lambda x: -x[3])
            for name, va, vb, d in deltas[:5]:
                delta_style = "red" if d > 0.1 else ("yellow" if d > 0.05 else "dim")
                val_text = Text()
                val_text.append(f"A={va:.3f}  ", style="cyan")
                val_text.append(f"B={vb:.3f}  ", style="magenta")
                val_text.append(f"\u0394{d:+.3f}", style=delta_style)
                table.add_row(name, val_text)
        else:
            table.add_row("", Text("no signal data at this step", style="dim"))

        return Group(header, table, Text("\n"))

    # ── Section: Focus Signals ──

    def _render_focus(self) -> Text:
        text = Text()
        if not self._focus_deltas:
            return text

        text.append("  Focus ", style="dim bold")
        parts = []
        for name, val in self._focus_deltas[:5]:
            arrow = "\u2191" if val > 0 else ("\u2193" if val < 0 else " ")
            sign = "+" if val >= 0 else ""
            parts.append(f"{name} {arrow}{sign}{val:.3f}")
        text.append("  ".join(parts))
        text.append("\n")
        return text
