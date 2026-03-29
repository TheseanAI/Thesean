"""Live run monitor — real-time pair telemetry during evaluation runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

if TYPE_CHECKING:
    from psystack.core.signal_schema import LivePairTelemetryView


@dataclass
class _EpisodeSnapshot:
    """Frozen final state of a completed episode."""

    episode: int
    pct_a: float
    pct_b: float
    done_a: bool
    done_b: bool
    term_a: str
    term_b: str
    rows_a: list[tuple[str, str]] = field(default_factory=list)
    rows_b: list[tuple[str, str]] = field(default_factory=list)


# How many recent step lines to keep per side
_STEP_LOG_DEPTH = 30


class LiveRunMonitor(Vertical):
    """Compact pair-compare telemetry display for live evaluation monitoring."""

    DEFAULT_CSS = """
    LiveRunMonitor {
        height: 1fr;
        border: round $panel;
        padding: 1 2;
    }
    LiveRunMonitor #lrm-header {
        height: auto;
        text-style: bold;
        color: $text;
        margin: 0 0 1 0;
    }
    LiveRunMonitor #lrm-history {
        height: auto;
        max-height: 12;
    }
    LiveRunMonitor .lrm-ep-done {
        height: auto;
        padding: 0 0 0 1;
        margin: 0 0 0 0;
    }
    LiveRunMonitor #lrm-sides {
        height: 1fr;
    }
    LiveRunMonitor .lrm-side-col {
        width: 1fr;
        height: 100%;
        border: round $panel;
        padding: 0;
        margin: 0 0 0 0;
    }
    LiveRunMonitor .lrm-side-col:first-child {
        margin: 0 1 0 0;
    }
    LiveRunMonitor .lrm-side-summary {
        height: auto;
        padding: 1 2;
        color: $text;
    }
    LiveRunMonitor .lrm-step-log {
        height: 1fr;
        border-top: hkey $panel;
        padding: 0 1;
        color: $text-muted;
    }
    LiveRunMonitor .lrm-step-line {
        height: 1;
        color: $text-muted;
    }
LiveRunMonitor #lrm-compare {
        height: auto;
        color: $text-muted;
        padding-top: 1;
    }
    """

    def __init__(self, *args, track_geometry: list[tuple[float, float]] | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._raster: BrailleTrackRaster | None = None
        if track_geometry:
            from psystack.tui.widgets.track_map import BrailleTrackRaster
            self._raster = BrailleTrackRaster(track_geometry)
        self._frozen: bool = False
        self._sidecar_status: str = "disabled"
        self._current_episode: int = -1
        self._completed: list[_EpisodeSnapshot] = []
        # Stash latest view so we can snapshot on episode change
        self._last_pct_a: float = 0.0
        self._last_pct_b: float = 0.0
        self._last_done_a: bool = False
        self._last_done_b: bool = False
        self._last_term_a: str = ""
        self._last_term_b: str = ""
        self._last_rows_a: list[tuple[str, str]] = []
        self._last_rows_b: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        self.border_title = "Live Monitor"
        yield Static("Waiting for evaluation to start...", id="lrm-header")
        yield VerticalScroll(id="lrm-history")
        with Horizontal(id="lrm-sides"):
            with Vertical(id="lrm-col-a", classes="lrm-side-col"):
                yield Static("", id="lrm-side-a", classes="lrm-side-summary")
                yield VerticalScroll(id="lrm-log-a", classes="lrm-step-log")
            with Vertical(id="lrm-col-b", classes="lrm-side-col"):
                yield Static("", id="lrm-side-b", classes="lrm-side-summary")
                yield VerticalScroll(id="lrm-log-b", classes="lrm-step-log")
        yield Static("", id="lrm-compare")

    def on_mount(self) -> None:
        self.query_one("#lrm-col-a").border_title = "Run A"
        self.query_one("#lrm-col-b").border_title = "Run B"

    def set_sidecar_status(self, status: str) -> None:
        self._sidecar_status = status

    def freeze(self) -> None:
        """Freeze display with completion message in header."""
        self._frozen = True
        self.border_title = "Computing Verdict"
        header = self.query_one("#lrm-header", Static)
        header.update(Text("Execution complete \u2014 computing verdict", style="bold yellow"))

    def _build_side(self, label: str, pct: float, done: bool, term: str, rows: list, tick: int = 0) -> Text:
        """Build Rich Text for one side (A or B) with a chunky progress bar."""
        try:
            half_width = max(self.size.width // 2 - 8, 20)
        except Exception:
            half_width = 30
        bar_width = min(half_width, 50)

        side = Text()
        side.append(f"{label}", style="bold")
        side.append(f"  t={tick}\n", style="dim")

        # Track map or block-character bar
        bar_color = "cyan" if label.strip() == "A" else "magenta"
        if self._raster:
            track_text = self._raster.render(pct, color=bar_color, dim_color="grey37")
            side.append_text(track_text)
            side.append(f"  {pct:.0%}", style="bold")
        else:
            filled = int(pct * bar_width)
            bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
            side.append(bar)
            side.append(f" {pct:.0%}", style="bold")
        if done:
            reason = f" [{term}]" if term else " [done]"
            side.append(reason, style="bold yellow")
        side.append("\n\n")

        for lbl, val in rows:
            side.append(f"  {lbl:12s}", style="dim")
            side.append(f"{val}\n")

        return side

    def _format_step_line(self, action: list[float], tick: int) -> Text:
        """Format a compact one-line step entry showing the action tuple."""
        text = Text()
        text.append(f"t={tick:<4d} ", style="dim")
        if action and len(action) >= 3:
            text.append("steer ", style="dim")
            text.append(f"{action[0]:+.2f}", style="")
            text.append("  thr ", style="dim")
            text.append(f"{action[1]:+.2f}", style="")
            text.append("  brk ", style="dim")
            text.append(f"{action[2]:+.2f}", style="")
            if len(action) > 3:
                extras = " ".join(f"{v:+.2f}" for v in action[3:])
                text.append(f"  {extras}", style="dim")
        elif action:
            text.append(" ".join(f"{v:+.2f}" for v in action), style="")
        else:
            text.append("no action", style="dim")
        return text

    def _append_step_line(self, log_id: str, line: Text) -> None:
        """Mount a new step line into the VerticalScroll log, trimming oldest if over capacity."""
        scroll = self.query_one(f"#{log_id}", VerticalScroll)
        # Trim oldest children (step lines or separators) if over capacity
        children = list(scroll.children)
        while len(children) >= _STEP_LOG_DEPTH:
            children[0].remove()
            children.pop(0)
        scroll.mount(Static(line, classes="lrm-step-line"))
        scroll.scroll_end(animate=False)

    def _build_completed_line(self, snap: _EpisodeSnapshot) -> Text:
        """Build a compact one-line summary for a completed episode."""
        text = Text()
        text.append(f"Ep {snap.episode}", style="bold")
        text.append("  ", style="")

        # Compact A bar
        text.append("A ", style="dim")
        filled_a = int(snap.pct_a * 12)
        text.append("\u2588" * filled_a + "\u2591" * (12 - filled_a), style="")
        text.append(f" {snap.pct_a:.0%}", style="bold")
        if snap.term_a:
            text.append(f" {snap.term_a}", style="dim")

        text.append("  ", style="")

        # Compact B bar
        text.append("B ", style="dim")
        filled_b = int(snap.pct_b * 12)
        text.append("\u2588" * filled_b + "\u2591" * (12 - filled_b), style="")
        text.append(f" {snap.pct_b:.0%}", style="bold")
        if snap.term_b:
            text.append(f" {snap.term_b}", style="dim")

        return text

    def _snapshot_current(self) -> None:
        """Snapshot the current episode into the completed list."""
        if self._current_episode < 0:
            return
        self._completed.append(_EpisodeSnapshot(
            episode=self._current_episode,
            pct_a=self._last_pct_a,
            pct_b=self._last_pct_b,
            done_a=self._last_done_a,
            done_b=self._last_done_b,
            term_a=self._last_term_a,
            term_b=self._last_term_b,
            rows_a=list(self._last_rows_a),
            rows_b=list(self._last_rows_b),
        ))
        # Mount the completed line into history
        history = self.query_one("#lrm-history", VerticalScroll)
        line = self._build_completed_line(self._completed[-1])
        idx = len(self._completed) - 1
        history.mount(Static(line, classes="lrm-ep-done", id=f"lrm-done-{idx}"))

    def push_step_only(self, view: LivePairTelemetryView) -> None:
        """Append step log lines without updating dashboard panels.

        Used for intermediate frames that were queued between poll cycles so
        every step appears in the log, not just the latest per poll.
        """
        if self._frozen:
            return
        self._handle_episode_change(view)
        line_a = self._format_step_line(view.action_a, view.tick)
        line_b = self._format_step_line(view.action_b, view.tick)
        self._append_step_line("lrm-log-a", line_a)
        self._append_step_line("lrm-log-b", line_b)

    def push_update(self, view: LivePairTelemetryView) -> None:
        """Render pair telemetry view into A/B columns with step log."""
        if self._frozen:
            return

        self._handle_episode_change(view)

        # Header
        header_text = Text()
        header_text.append(f"Episode {view.episode}/{view.episode_total}", style="bold")
        if self._sidecar_status != "disabled":
            header_text.append(f"  Sidecar: {self._sidecar_status}", style="dim")

        # Per-side track progress (fall back to step-based if adapter doesn't provide it)
        step_pct = min(view.tick / view.max_ticks, 1.0) if view.max_ticks > 0 else 0.0

        disp_a = 1.0 if view.done_a else (view.progress_a if view.progress_a > 0 else step_pct)
        disp_b = 1.0 if view.done_b else (view.progress_b if view.progress_b > 0 else step_pct)

        side_a = self._build_side("A", disp_a, view.done_a, view.term_a or "", view.rows_a, tick=view.tick)
        side_b = self._build_side("B", disp_b, view.done_b, view.term_b or "", view.rows_b, tick=view.tick)

        # Stash for snapshot
        self._last_pct_a = disp_a
        self._last_pct_b = disp_b
        self._last_done_a = view.done_a
        self._last_done_b = view.done_b
        self._last_term_a = view.term_a or ""
        self._last_term_b = view.term_b or ""
        self._last_rows_a = list(view.rows_a)
        self._last_rows_b = list(view.rows_b)

        line_a = self._format_step_line(view.action_a, view.tick)
        line_b = self._format_step_line(view.action_b, view.tick)

        # Compare strip
        compare_text = Text()
        if view.compare_rows:
            parts = [f"{lbl} {val}" for lbl, val in view.compare_rows]
            compare_text.append("  ".join(parts), style="dim")

        with self.app.batch_update():
            self.query_one("#lrm-header", Static).update(header_text)
            self.query_one("#lrm-col-a").border_title = f"Run A \u2014 Ep {view.episode}"
            self.query_one("#lrm-col-b").border_title = f"Run B \u2014 Ep {view.episode}"
            self.query_one("#lrm-side-a", Static).update(side_a)
            self.query_one("#lrm-side-b", Static).update(side_b)
            self.query_one("#lrm-compare", Static).update(compare_text)

        # Mount step lines outside batch_update — Textual can't mount+query in same batch
        self._append_step_line("lrm-log-a", line_a)
        self._append_step_line("lrm-log-b", line_b)

    def _handle_episode_change(self, view: LivePairTelemetryView) -> None:
        """Detect episode change — snapshot previous episode, clear logs for fresh start."""
        if view.episode != self._current_episode:
            self._snapshot_current()
            self._current_episode = view.episode
            for log_id in ("lrm-log-a", "lrm-log-b"):
                scroll = self.query_one(f"#{log_id}", VerticalScroll)
                for w in list(scroll.children):
                    w.remove()

    def clear(self) -> None:
        """Reset to waiting state."""
        self._frozen = False
        self._sidecar_status = "disabled"
        self._current_episode = -1
        self._completed.clear()
        self.border_title = "Live Monitor"
        with self.app.batch_update():
            self.query_one("#lrm-header", Static).update(
                "Waiting for evaluation to start..."
            )
            self.query_one("#lrm-side-a", Static).update("")
            self.query_one("#lrm-side-b", Static).update("")
            self.query_one("#lrm-compare", Static).update("")
            # Clear history
            history = self.query_one("#lrm-history", VerticalScroll)
            for widget in list(history.query(".lrm-ep-done")):
                widget.remove()
            # Clear step logs
            for log_id in ("lrm-log-a", "lrm-log-b"):
                scroll = self.query_one(f"#{log_id}", VerticalScroll)
                for w in list(scroll.children):
                    w.remove()
