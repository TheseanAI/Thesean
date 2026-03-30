"""Investigation Screen — 3-panel investigation workbench."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from thesean.models.episode import OutcomeSummary

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static as _Static

from thesean.models.case import Case
from thesean.models.event import Event
from thesean.tui.state import CaseState, ScreenMode, screen_mode_from_case_state
from thesean.tui.widgets.case_bar import CaseBar
from thesean.tui.widgets.event_navigator import EventNavigator
from thesean.tui.widgets.help_overlay import HelpOverlay
from thesean.tui.widgets.live_run_monitor import LiveRunMonitor
from thesean.tui.widgets.progress_summary import ProgressSummary
from thesean.tui.widgets.step_inspector import StepInspector
from thesean.tui.widgets.transport_bar import TransportBar

# Pre-compute CSS class names for all screen modes
_MODE_CLASSES = tuple(f"state-{m.value.replace('_', '-')}" for m in ScreenMode)

# Action gating sets
_READY_ONLY_ACTIONS = frozenset({
    "open_attribution", "cycle_signal",
    "next_event", "prev_event",
    "step_forward", "step_backward", "step_forward_10", "step_backward_10",
    "next_episode", "prev_episode",
    "analysis_rerun",
})

_RUNNING_ONLY_ACTIONS = frozenset({
    "cycle_live_view",
    "cancel_run",
})


class InvestigationScreen(Screen):
    """Main investigation screen with 3-column layout + transport bar."""

    BINDINGS = [
        Binding("h", "toggle_help", "Help", show=False),
        Binding("r", "run_evaluation", "Run eval", show=False),
        Binding("j", "next_event", "Next event", show=False),
        Binding("k", "prev_event", "Prev event", show=False),
        Binding("comma", "step_backward", "Step back", show=False),
        Binding("l", "step_forward", "Step forward", show=False),
        Binding(".", "step_forward", "Step forward", show=False),
        Binding("H", "step_backward_10", "Step back 10", show=False),
        Binding("L", "step_forward_10", "Step forward 10", show=False),
        Binding("left_square_bracket", "prev_event", "Prev event", show=False),
        Binding("right_square_bracket", "next_event", "Next event", show=False),
        Binding("m", "cycle_signal", "Signal", show=False),
        Binding("n", "next_episode", "Next ep", show=False),
        Binding("N", "prev_episode", "Prev ep", show=False),
        Binding("a", "open_attribution", "Attribution", show=False),
        Binding("b", "open_builder", "Builder", show=False),
        Binding("A", "analysis_rerun", "Reanalyze", show=False),
        Binding("E", "edit_case", "Edit case", show=False),
        Binding("x", "export_report", "Export", show=False),
        Binding("e", "open_evidence", "Evidence", show=False),
        Binding("c", "open_context", "Context", show=False),
        Binding("v", "cycle_live_view", "Live view", show=False),
        Binding("escape", "dismiss_or_cancel", "Back", show=False),
    ]

    DEFAULT_CSS = """
    InvestigationScreen {
        layout: vertical;
    }
    InvestigationScreen #inv-main {
        height: 1fr;
    }
    InvestigationScreen #inv-center {
        width: 1fr;
    }
    InvestigationScreen #inv-right {
        width: 34;
    }
    InvestigationScreen #inv-help-hint {
        dock: bottom;
        height: 1;
        padding: 0 1;
        color: $text-muted;
        background: $boost;
    }
    InvestigationScreen LiveRunMonitor {
        display: none;
    }
    InvestigationScreen.state-running-live LiveRunMonitor {
        display: block;
    }
    InvestigationScreen.state-running-live ProgressSummary {
        display: none;
    }
    InvestigationScreen.state-draft-empty ProgressSummary {
        display: none;
    }
    """

    def __init__(
        self,
        case: Case | None = None,
        case_state: CaseState = CaseState.DRAFT,
        events: list[Event] | None = None,
        divergence_scores: list[float] | None = None,
        values_a: list[float] | None = None,
        values_b: list[float] | None = None,
        signals_a: dict[int, dict[str, float]] | None = None,
        signals_b: dict[int, dict[str, float]] | None = None,
        max_step: int = 0,
        metric_ids: list[str] | None = None,
        all_metrics_data: dict[str, tuple[list[float], list[float], list[float]]] | None = None,
        outcomes: OutcomeSummary | None = None,
        episode_idx: int = 0,
        episode_count: int = 0,
        stale: bool = False,
        signal_schema: Any = None,
        signal_translator: Any = None,
        track_geometry: list[tuple[float, float]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._track_geometry = track_geometry
        self._case = case
        self._case_state = case_state
        self._screen_mode = screen_mode_from_case_state(case_state)
        self._outcomes = outcomes
        self._events = events or []
        self._divergence_scores = divergence_scores or []
        self._values_a = values_a or []
        self._values_b = values_b or []
        self._signals_a: dict[int, dict[str, float]] = signals_a or {}
        self._signals_b: dict[int, dict[str, float]] = signals_b or {}
        self._max_step = max_step
        # Signal cycling support
        self._signal_names = metric_ids or []
        self._active_signal_idx = 0
        self._all_metrics_data = all_metrics_data or {}
        # Episode cycling
        self._episode_idx = episode_idx
        self._episode_count = episode_count
        self._rerun_confirmed: bool = False
        self._stale = stale
        # Event selection
        self._selected_event_idx: int | None = None
        self._sorted_events: list[Event] = []
        self._step_to_event_idx: dict[int, int] = {}
        # Adapter-agnostic schema
        self._signal_schema = signal_schema
        self._signal_translator = signal_translator
        self._cancel_confirmed: bool = False

    def compose(self) -> ComposeResult:
        yield CaseBar(id="inv-case-bar")
        with Horizontal(id="inv-main"):
            # Center canvas
            with Vertical(id="inv-center"):
                yield LiveRunMonitor(track_geometry=self._track_geometry)
                yield ProgressSummary(track_geometry=self._track_geometry)

            # Right rail
            with Vertical(id="inv-right"):
                yield EventNavigator()
                yield StepInspector()

        yield TransportBar()
        yield HelpOverlay()
        yield _Static("h = help", id="inv-help-hint")

    # ── Screen mode management ──

    def set_screen_mode(self, mode: ScreenMode) -> None:
        """Set display mode — drives CSS visibility, keybinding gating, and timeline."""
        self._screen_mode = mode
        self._cancel_confirmed = False
        for cls in _MODE_CLASSES:
            self.remove_class(cls)
        self.add_class(f"state-{mode.value.replace('_', '-')}")
        if mode != ScreenMode.RUNNING_LIVE:
            self.query_one(LiveRunMonitor).clear()
        self.refresh_bindings()

    def action_toggle_help(self) -> None:
        """Toggle the help command overlay."""
        self.query_one(HelpOverlay).toggle()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:  # type: ignore[override]
        """Gate actions based on screen mode."""
        if action in _READY_ONLY_ACTIONS:
            return True if self._screen_mode == ScreenMode.READY_INVESTIGATION else None
        if action in _RUNNING_ONLY_ACTIONS:
            return True if self._screen_mode == ScreenMode.RUNNING_LIVE else None
        if action == "export_report":
            ws = getattr(getattr(self.app, "state", None), "current_workspace", None)
            if not ws:
                return False
            return bool((ws / "analysis" / "result.json").exists())
        return True

    def on_mount(self) -> None:
        # Case bar — investigation header
        case_bar = self.query_one(CaseBar)
        if self._case:
            case_bar.set_investigation(
                self._case,
                self._episode_idx,
                self._episode_count,
                self._outcomes,
                stale=self._stale,
            )
        else:
            case_bar.update("No case loaded")

        # Events — sort temporally (suggested investigation path)
        _SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}
        if self._events:
            self._sorted_events = sorted(
                self._events,
                key=lambda e: (e.step, _SEVERITY_RANK.get(e.severity, 99), -e.score),
            )
        else:
            self._sorted_events = []
        self._build_step_index()
        self.query_one(EventNavigator).set_events(self._sorted_events)

        # Transport
        transport = self.query_one(TransportBar)
        transport.max_step = self._max_step
        if self._episode_count > 0:
            from textual.widgets import Static
            range_label = transport.query_one("#tb-range", Static)
            range_label.update(f"Ep {self._episode_idx + 1}/{self._episode_count}  / {self._max_step}")

        # Wire schema to widgets
        self.query_one(StepInspector).set_schema(self._signal_schema)
        self.query_one(ProgressSummary).set_schema(self._signal_schema, self._signal_translator)

        # Progress summary
        self.query_one(ProgressSummary).set_data(
            self._signals_a, self._signals_b, self._sorted_events, self._max_step
        )

        # Apply screen mode (drives CSS classes + binding gating)
        self.set_screen_mode(self._screen_mode)

        # Select first event (drives transport, timeline, panels, focus line)
        if self._sorted_events:
            self._select_event(0)
        else:
            self._render_focus_line()

    # ── Event selection (coordination hub) ──

    def _select_event(self, idx: int | None) -> None:
        """Single coordination point for event selection."""
        if idx == self._selected_event_idx:
            return
        self._selected_event_idx = idx
        self.query_one(EventNavigator).highlight(idx)
        if idx is not None and 0 <= idx < len(self._sorted_events):
            evt = self._sorted_events[idx]
            self.query_one(TransportBar).goto_step(evt.step)
            # Update ProgressSummary with event's active signals
            if hasattr(evt, "active_signals") and evt.active_signals:
                deltas = [(s.name, s.value) for s in evt.active_signals]
                self.query_one(ProgressSummary).set_focus_signals(deltas)
        self._render_focus_line()

    def _build_step_index(self) -> None:
        """Map step -> event index for auto-select on scrub."""
        self._step_to_event_idx = {}
        for i, evt in enumerate(self._sorted_events):
            if evt.step not in self._step_to_event_idx:
                self._step_to_event_idx[evt.step] = i

    # ── Focus line ──

    def _render_focus_line(self) -> None:
        """Build focus signals line below the timeline."""
        text = Text()
        text.append("Focus: ", style="dim")

        if self._selected_event_idx is not None and self._sorted_events:
            evt = self._sorted_events[self._selected_event_idx]
            if hasattr(evt, "active_signals") and evt.active_signals:
                signals = evt.active_signals
                if isinstance(signals, dict):
                    items = list(signals.items())[:5]
                else:
                    items = [(s.name, s.value) for s in signals[:5]]
                parts = []
                for name, val in items:
                    arrow = "\u2191" if val > 0 else ("\u2193" if val < 0 else " ")
                    parts.append(f"{name} {arrow}{val:+.2f}")
                text.append(" | ".join(parts), style="")
            else:
                text.append("--", style="dim")
        else:
            text.append("no event selected", style="dim")

        try:
            self.query_one("#inv-focus-line", _Static).update(text)
        except Exception:
            pass

    # ── Case bar ──

    def _refresh_case_bar(self) -> None:
        """Update case bar with current state."""
        if not self._case:
            return
        try:
            self.query_one(CaseBar).set_investigation(
                self._case,
                self._episode_idx,
                self._episode_count,
                self._outcomes,
                stale=self._stale,
            )
        except Exception:
            pass

    def push_live_step_only(self, view: object) -> None:
        """Forward step-only log line to the LiveRunMonitor widget."""
        if self._screen_mode == ScreenMode.RUNNING_LIVE:
            self.query_one(LiveRunMonitor).push_step_only(view)  # type: ignore[arg-type]

    def push_live_update(self, view: object) -> None:
        """Forward live telemetry to the LiveRunMonitor widget."""
        if self._screen_mode == ScreenMode.RUNNING_LIVE:
            self.query_one(LiveRunMonitor).push_update(view)  # type: ignore[arg-type]

    def update_progress(self, side: str, episode: int, total: int) -> None:
        """Update case bar with eval progress (called from app.py)."""
        try:
            bar = self.query_one(CaseBar)
            text = Text()
            text.append("Running", style="bold yellow")
            text.append(f" \u2502 Side {side.upper()}: {episode}/{total}", style="")
            if self._episode_count > 0:
                text.append(f" \u2502 Ep {self._episode_idx + 1}/{self._episode_count}", style="dim")
            bar.update(text)
        except Exception:
            pass

    # ── Data helpers ──

    def _get_signals_at_step(self, step: int) -> tuple[dict[str, float] | None, dict[str, float] | None]:
        sa = self._signals_a.get(step)
        sb = self._signals_b.get(step)
        return sa, sb

    def _find_event_at_step(self, step: int) -> Event | None:
        for evt in self._events:
            if evt.step == step:
                return evt
        return None

    def _update_panels_at_step(self, step: int) -> None:
        """Propagate step change to StepInspector and ProgressSummary."""
        sa, sb = self._get_signals_at_step(step)
        evt = self._find_event_at_step(step)

        hypothesis: str | None = None
        if evt:
            hypothesis = _derive_hypothesis(evt, self._events)

        self.query_one(StepInspector).update_step(step, sa, sb, evt, hypothesis=hypothesis)
        self.query_one(ProgressSummary).update_step(step, sa, sb)

        # Update ProgressSummary with focus signals
        ps = self.query_one(ProgressSummary)
        if evt and hasattr(evt, "active_signals") and evt.active_signals:
            ps.set_focus_signals([(s.name, s.value) for s in evt.active_signals])
        elif sa and sb:
            deltas = []
            for key in sa:
                if key in sb:
                    deltas.append((key, sa[key] - sb[key]))
            deltas.sort(key=lambda x: abs(x[1]), reverse=True)
            ps.set_focus_signals(deltas[:5])

        self._render_focus_line()

    # ── Transport messages ──

    def on_transport_bar_step_changed(self, event: TransportBar.StepChanged) -> None:
        self._update_panels_at_step(event.step)

        event_idx = self._step_to_event_idx.get(event.step)
        if event_idx is not None and event_idx != self._selected_event_idx:
            self._selected_event_idx = event_idx
            self.query_one(EventNavigator).highlight(event_idx)
            self._render_focus_line()

    def on_transport_bar_event_selected(self, event: TransportBar.EventSelected) -> None:
        if event.event_idx > 0:
            self.action_next_event()
        else:
            self.action_prev_event()

    def on_transport_bar_episode_nav(self, msg: TransportBar.EpisodeNav) -> None:
        if msg.direction > 0:
            self.action_next_episode()
        else:
            self.action_prev_episode()

    def on_transport_bar_cycle_requested(self, msg: TransportBar.CycleRequested) -> None:
        dispatch = {
            "signal": self.action_cycle_signal,
        }
        handler = dispatch.get(msg.target)
        if handler:
            handler()

    def on_event_navigator_event_clicked(self, event: EventNavigator.EventClicked) -> None:
        self._select_event(event.event_idx)

    # ── Key actions ──

    def action_run_evaluation(self) -> None:
        app = self.app
        if not hasattr(app, 'state'):
            return

        from thesean.tui.state import CaseState
        case_state = app.state.case_state

        if case_state == CaseState.RUNNING:
            self.notify("Evaluation already in progress.")
            return
        elif case_state == CaseState.READY:
            if not getattr(self, '_rerun_confirmed', False):
                self.notify("Previous results exist. Press r again to re-run (will overwrite).")
                self._rerun_confirmed = True
                return
            self._rerun_confirmed = False
        elif case_state in (CaseState.DRAFT, CaseState.RUN_FAILED):
            pass
        else:
            return

        self.notify("Starting evaluation...")
        app.run_evaluation()  # type: ignore[attr-defined]

    def action_next_event(self) -> None:
        if not self._sorted_events:
            return
        if self._selected_event_idx is None:
            self._select_event(0)
        elif self._selected_event_idx < len(self._sorted_events) - 1:
            self._select_event(self._selected_event_idx + 1)

    def action_prev_event(self) -> None:
        if not self._sorted_events:
            return
        if self._selected_event_idx is None:
            self._select_event(len(self._sorted_events) - 1)
        elif self._selected_event_idx > 0:
            self._select_event(self._selected_event_idx - 1)

    def action_step_forward(self) -> None:
        self.query_one(TransportBar).step_forward()

    def action_step_backward(self) -> None:
        self.query_one(TransportBar).step_backward()

    def action_step_forward_10(self) -> None:
        self.query_one(TransportBar).step_forward(10)

    def action_step_backward_10(self) -> None:
        self.query_one(TransportBar).step_backward(10)

    def action_cycle_signal(self) -> None:
        if not self._signal_names:
            self.notify("No signals available")
            return
        self._active_signal_idx = (self._active_signal_idx + 1) % len(self._signal_names)
        signal_name = self._signal_names[self._active_signal_idx]

        values_a = [self._signals_a.get(s, {}).get(signal_name, 0.0) for s in sorted(self._signals_a.keys())]
        values_b = [self._signals_b.get(s, {}).get(signal_name, 0.0) for s in sorted(self._signals_b.keys())]
        min_len = min(len(values_a), len(values_b))
        div = [abs(values_a[i] - values_b[i]) for i in range(min_len)]

        self._values_a = values_a
        self._values_b = values_b
        self._divergence_scores = div

        group_label = ""
        schema = self._signal_schema
        if schema:
            for g in schema.group_order:
                for sig_def in schema.groups.get(g, []):
                    if sig_def.name == signal_name:
                        group_label = g
                        break
                if group_label:
                    break
        self.notify(f"Signal: {signal_name} ({self._active_signal_idx + 1}/{len(self._signal_names)}) [{group_label}]")
        self.query_one(TransportBar).update_cycle_label("signal", f"Sig: {signal_name}")

    def action_next_episode(self) -> None:
        if self._episode_count <= 1:
            return
        self._episode_idx = (self._episode_idx + 1) % self._episode_count
        self._reload_episode_data()
        self.notify(f"Episode {self._episode_idx + 1}/{self._episode_count}")

    def action_prev_episode(self) -> None:
        if self._episode_count <= 1:
            return
        self._episode_idx = (self._episode_idx - 1) % self._episode_count
        self._reload_episode_data()
        self.notify(f"Episode {self._episode_idx + 1}/{self._episode_count}")

    def _reload_episode_data(self) -> None:
        app = self.app
        if not hasattr(app, 'backend') or not hasattr(app, 'state'):
            return
        ws = app.state.current_workspace
        if not ws:
            return

        app.state.selected_episode_idx = self._episode_idx
        app.state.selected_run_id = f"ep_{self._episode_idx:04d}"

        translator = self._signal_translator
        self._signals_a = app.backend.load_episode_signals(ws, "a", self._episode_idx, translator=translator)
        self._signals_b = app.backend.load_episode_signals(ws, "b", self._episode_idx, translator=translator)

        max_a = max(self._signals_a.keys(), default=0)
        max_b = max(self._signals_b.keys(), default=0)
        self._max_step = max(max_a, max_b)

        signal_name = self._signal_names[self._active_signal_idx] if self._signal_names else "steering"
        self._values_a = [self._signals_a.get(s, {}).get(signal_name, 0.0) for s in sorted(self._signals_a.keys())]
        self._values_b = [self._signals_b.get(s, {}).get(signal_name, 0.0) for s in sorted(self._signals_b.keys())]
        min_len = min(len(self._values_a), len(self._values_b))
        self._divergence_scores = [abs(self._values_a[i] - self._values_b[i]) for i in range(min_len)]

        ep_id = f"ep_{self._episode_idx:04d}"
        self._events = app.backend.load_events(ws, episode_id=ep_id)

        _SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}
        if self._events:
            self._sorted_events = sorted(
                self._events,
                key=lambda e: (e.step, _SEVERITY_RANK.get(e.severity, 99), -e.score),
            )
        else:
            self._sorted_events = []
        self._build_step_index()
        self.query_one(EventNavigator).set_events(self._sorted_events)

        self.query_one(ProgressSummary).set_data(
            self._signals_a, self._signals_b, self._sorted_events, self._max_step
        )

        transport = self.query_one(TransportBar)
        transport.max_step = self._max_step
        from textual.widgets import Static
        range_label = transport.query_one("#tb-range", Static)
        range_label.update(f"Ep {self._episode_idx + 1}/{self._episode_count}  / {self._max_step}")

        self._refresh_case_bar()

        self._selected_event_idx = None
        if self._sorted_events:
            self._select_event(0)
        else:
            transport.goto_step(0)
            self._update_panels_at_step(0)
            self._render_focus_line()

    def action_analysis_rerun(self) -> None:
        app = self.app
        if hasattr(app, 'run_analysis_only'):
            app.run_analysis_only()

    def action_edit_case(self) -> None:
        app = self.app
        if hasattr(app, '_open_run_builder_edit'):
            app._open_run_builder_edit()

    def action_open_attribution(self) -> None:
        if hasattr(self.app, "_open_attribution"):
            self.app._open_attribution()  # type: ignore[attr-defined]

    def action_open_builder(self) -> None:
        if hasattr(self.app, "_open_run_builder"):
            self.app._open_run_builder()

    def action_export_report(self) -> None:
        app = self.app
        if hasattr(app, "export_report"):
            app.export_report()

    def action_cycle_live_view(self) -> None:
        app = self.app
        if not hasattr(app, "state"):
            return
        cycle = ["none", "tui", "sidecar", "both"]
        current = app.state.live_view
        try:
            idx = cycle.index(current)
        except ValueError:
            idx = 0
        next_val = cycle[(idx + 1) % len(cycle)]
        app.state.live_view = next_val
        ws = app.state.current_workspace
        if ws:
            from thesean.pipeline.workspace import read_workspace_state, write_workspace_state
            ws_state = read_workspace_state(ws)
            ws_state["live_view"] = next_val
            write_workspace_state(ws, ws_state)
        self.notify(f"Live view: {next_val}")

    def action_open_evidence(self) -> None:
        from thesean.tui.screens.drawers.evidence_drawer import EvidenceDrawer
        self.app.push_screen(EvidenceDrawer(events=self._events))

    def action_dismiss_or_cancel(self) -> None:
        """Escape key: cancel run if running, otherwise pop screen."""
        if self._screen_mode == ScreenMode.RUNNING_LIVE:
            self.action_cancel_run()
        else:
            self.app.pop_screen()

    def action_cancel_run(self) -> None:
        """Prompt for confirmation, then cancel the running evaluation."""
        if self._screen_mode != ScreenMode.RUNNING_LIVE:
            return
        if getattr(self, "_cancel_confirmed", False):
            self._cancel_confirmed = False
            if hasattr(self.app, "cancel_evaluation"):
                self.app.cancel_evaluation()
        else:
            self._cancel_confirmed = True
            self.notify("Press Esc again to cancel the running evaluation.")

    def action_open_context(self) -> None:
        from thesean.tui.screens.drawers.context_drawer import ContextDrawer
        self.app.push_screen(ContextDrawer(case=self._case))


def _derive_hypothesis(event: Event, all_events: list[Event]) -> str:
    """Derive a short hypothesis string from event context."""
    nearby = [e for e in all_events if abs(e.step - event.step) <= 5 and e.id != event.id]

    if event.type == "first_signal_divergence" and any(
        e.type == "first_action_divergence" for e in nearby
    ):
        return "WM drift precedes planner action split"
    if event.type == "first_action_divergence" and any(
        e.type == "first_signal_divergence" for e in nearby
    ):
        return "Planner divergence follows signal drift"
    if event.type == "first_risk_spike":
        return "Risk spike indicates potential boundary instability"
    if event.type == "first_boundary_collapse":
        return "Boundary collapse — safety constraint violated"
    if event.type == "terminal":
        return "Terminal event — run ended"
    if event.type == "max_metric_gap":
        return "Peak metric divergence between runs"
    if event.type == "first_divergence":
        return "Core signal divergence — policies respond differently"
    if event.type == "divergence_window":
        dur = event.metadata.get("duration", 0) if event.metadata else 0
        if dur > 20:
            return f"Sustained divergence ({dur} steps) — models in different regimes"
        return f"Divergence window ({dur} steps) — policies split then reconverge"
    if event.type == "risk_spike":
        return "Risk spike — approaching track boundary"
    if event.type == "off_track_terminal":
        return "Off-track terminal — run ended due to boundary violation"
    if event.type == "max_gap":
        return "Peak reward divergence between runs"

    return f"{event.type.replace('_', ' ').title()} detected"
