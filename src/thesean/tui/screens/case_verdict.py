"""CaseVerdictScreen — case-level verdict and episode drill-down."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from thesean.core.signal_schema import LivePairTelemetryView
    from thesean.models.episode import OutcomeSummary

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from thesean.models.case import Case
from thesean.models.event import Event
from thesean.tui.state import CaseState
from thesean.tui.widgets.action_bar import ActionBar
from thesean.tui.widgets.case_bar import CaseBar
from thesean.tui.widgets.live_run_monitor import LiveRunMonitor

_CV_BUTTONS = [
    ("Run Eval", "cv-btn-run", "primary"),
    ("Reanalyze", "cv-btn-reanalyze", "default"),
    ("Investigate", "cv-btn-investigate", "primary"),
    ("Edit Case", "cv-btn-edit", "default"),
    ("Export", "cv-btn-export", "default"),
    ("Attribution", "cv-btn-attribution", "default"),
    ("Builder", "cv-btn-builder", "default"),
    ("Back", "cv-btn-back", "default"),
]

_MODE_CSS = {
    "idle": "cv-draft",
    "running": "cv-running",
    "pending": "cv-pending",
    "ready": "cv-ready",
    "stale": "cv-stale",
    "failed": "cv-draft",
}


class CaseVerdictScreen(Screen):
    """Case-level verdict with episode table for drill-down."""

    BINDINGS = [
        Binding("enter", "select_episode", "Investigate", show=True),
        Binding("r", "run_evaluation", "Run eval", show=True),
        Binding("A", "analysis_rerun", "Reanalyze", show=True),
        Binding("E", "edit_case", "Edit case", show=True),
        Binding("x", "export_report", "Export", show=True),
        Binding("a", "open_attribution", "Attribution", show=True),
        Binding("I", "run_isolation", "Isolate", show=True),
        Binding("b", "open_builder", "Builder", show=True),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    DEFAULT_CSS = """
    CaseVerdictScreen {
        layout: vertical;
    }

    /* ── Verdict hero block ── */
    CaseVerdictScreen #cv-verdict-block {
        height: auto;
        min-height: 3;
        padding: 0 2;
        margin: 0 1;
        border: round $panel;
        border-title-style: bold;
    }
    CaseVerdictScreen #cv-verdict-block.cv-vb-regression {
        border: round $error;
        border-title-color: $error;
    }
    CaseVerdictScreen #cv-verdict-block.cv-vb-improvement {
        border: round $secondary;
        border-title-color: $secondary;
    }
    CaseVerdictScreen #cv-verdict-block.cv-vb-nochange {
        border: round $panel;
        border-title-color: $text-muted;
    }

/* ── Draft body ── */
    CaseVerdictScreen #cv-draft-body {
        height: auto;
        padding: 1 2;
        color: $text-muted;
        text-align: center;
    }

    /* ── Episode table wrapper ── */
    CaseVerdictScreen #cv-table-wrapper {
        height: 1fr;
        border: round $panel;
        margin: 0 1;
        background: $background;
    }
    CaseVerdictScreen #cv-table-wrapper:focus-within {
        border: round $primary;
        border-title-color: $primary;
    }
    CaseVerdictScreen #cv-episode-table {
        height: 1fr;
    }

    /* ── Empty state ── */
    CaseVerdictScreen #cv-empty-state {
        display: none;
        height: 1fr;
        padding: 4 8;
        text-align: center;
        color: $text-muted;
        content-align: center middle;
    }

    /* ── Default: hide optional sections ── */
    CaseVerdictScreen LiveRunMonitor { display: none; }
    CaseVerdictScreen #cv-draft-body { display: none; }
    CaseVerdictScreen #cv-table-wrapper { display: none; }
    /* DRAFT */
    CaseVerdictScreen.cv-draft #cv-draft-body { display: block; }

    /* RUNNING */
    CaseVerdictScreen.cv-running LiveRunMonitor { display: block; }

    /* PENDING */
    CaseVerdictScreen.cv-pending LiveRunMonitor { display: block; }

    /* READY */
    CaseVerdictScreen.cv-ready #cv-table-wrapper { display: block; }

    /* STALE */
    CaseVerdictScreen.cv-stale #cv-table-wrapper { display: block; }

    /* EMPTY (draft + no episodes) */
    CaseVerdictScreen.cv-empty #cv-empty-state { display: block; }
    CaseVerdictScreen.cv-empty #cv-table-wrapper { display: none; }
    CaseVerdictScreen.cv-empty #cv-draft-body { display: none; }

    /* ── Verdict action row ── */
    CaseVerdictScreen #cv-verdict-actions {
        height: auto;
        padding: 0 2;
        margin: 1 1;
        align: left middle;
    }
    CaseVerdictScreen #cv-verdict-actions Button {
        min-width: 10;
        height: 1;
        margin: 0 1 0 0;
    }

    /* ── Table action row ── */
    CaseVerdictScreen #cv-table-actions {
        height: auto;
        padding: 0 2;
        margin: 1 1;
        align: left middle;
        display: none;
    }
    CaseVerdictScreen #cv-table-actions Button {
        min-width: 12;
        height: 1;
        margin: 0 1 0 0;
    }
    CaseVerdictScreen.cv-ready #cv-table-actions { display: block; }
    CaseVerdictScreen.cv-stale #cv-table-actions { display: block; }
    """

    class EpisodeSelected(Message):
        def __init__(self, episode_idx: int) -> None:
            self.episode_idx = episode_idx
            super().__init__()

    def __init__(
        self,
        case: Case | None = None,
        case_state: CaseState = CaseState.DRAFT,
        outcomes: OutcomeSummary | None = None,
        episode_count: int = 0,
        events_by_episode: dict[str, list[Event]] | None = None,
        stale: bool = False,
        track_geometry: list[tuple[float, float]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._case = case
        self._track_geometry = track_geometry
        self._case_state = case_state
        self._outcomes = outcomes
        self._episode_count = episode_count
        self._events_by_episode = events_by_episode or {}
        self._stale = stale
        # Screen mode state
        self._screen_mode: str = "idle"  # idle | running | pending | ready | failed | stale
        self._progress_side: str = ""
        self._progress_episode: int = 0
        self._progress_total: int = 0
        self._error_message: str = ""
        # Episode selection toggle
        self._selected_episode_row: int | None = None
        # Live monitoring state
        self._sidecar_status: str = "disabled"
        self._last_live_view: LivePairTelemetryView | None = None
        self._live_view_mode: str = "tui"

    def compose(self) -> ComposeResult:
        yield CaseBar(id="cv-case-bar")
        yield Static("", id="cv-verdict-block")
        # Contextual verdict actions — Run/Reanalyze/Edit near the verdict
        with Horizontal(id="cv-verdict-actions"):
            yield Button("Run Eval", id="cv-ctx-run", variant="primary")
            yield Button("Reanalyze", id="cv-ctx-reanalyze")
            yield Button("Edit Case", id="cv-ctx-edit")
            yield Button("Export", id="cv-ctx-export")
        yield LiveRunMonitor(track_geometry=self._track_geometry)
        yield Static("", id="cv-draft-body")
        yield Static(
            "[dim]\u25cb[/dim]  No episode data yet\n\n"
            "Press [bold]r[/bold] to run evaluation",
            id="cv-empty-state",
        )
        with Vertical(id="cv-table-wrapper"):
            yield DataTable(id="cv-episode-table")
        # Contextual table actions — Investigate near the episode table
        with Horizontal(id="cv-table-actions"):
            yield Button("Investigate Selected", id="cv-ctx-investigate", variant="primary")
            yield Button("Attribution", id="cv-ctx-attribution")
            yield Button("Isolate", id="cv-ctx-isolate")
        yield ActionBar(_CV_BUTTONS)
        yield Footer()

    def on_mount(self) -> None:
        # Case bar
        case_bar = self.query_one(CaseBar)
        if self._case:
            case_bar.set_case(self._case, case_state=self._case_state.value)
        else:
            case_bar.update("No case loaded")

        # Derive initial screen mode from case_state
        if self._outcomes and not self._stale:
            self._screen_mode = "ready"
        elif self._stale:
            self._screen_mode = "stale"
        elif self._case_state in (CaseState.DRAFT, CaseState.RUN_FAILED):
            self._screen_mode = "idle"
        elif self._case_state == CaseState.RUNNING:
            self._screen_mode = "running"
        elif self._case_state == CaseState.ANALYSIS_PARTIAL:
            self._screen_mode = "failed"
        else:
            self._screen_mode = "idle"

        self._refresh()

    # ── Public semantic methods ──

    def set_running(self, sidecar_status: str = "disabled", live_view: str = "tui") -> None:
        self._screen_mode = "running"
        self._sidecar_status = sidecar_status
        self._live_view_mode = live_view
        self.query_one(LiveRunMonitor).set_sidecar_status(sidecar_status)
        self._refresh()

    def set_progress(self, side: str, episode: int, total: int) -> None:
        self._progress_side = side
        self._progress_episode = episode
        self._progress_total = total
        self._screen_mode = "running"
        self._refresh()

    def set_pending(self) -> None:
        self._screen_mode = "pending"
        self.query_one(LiveRunMonitor).freeze()
        self._refresh()

    def set_failed(self, error: str) -> None:
        self._case_state = CaseState.RUN_FAILED
        self._error_message = error
        self._screen_mode = "failed"
        self._refresh()

    def set_ready(
        self, outcomes: OutcomeSummary, episode_count: int, events_by_episode: dict[str, list[Event]]
    ) -> None:
        self._case_state = CaseState.READY
        self._outcomes = outcomes
        self._episode_count = episode_count
        self._events_by_episode = events_by_episode
        self._stale = False
        self._screen_mode = "ready"
        self._refresh()

    def set_stale(self, outcomes: OutcomeSummary) -> None:
        self._outcomes = outcomes
        self._stale = True
        self._screen_mode = "stale"
        self._refresh()

    def push_live_step_only(self, view: Any) -> None:
        if self._screen_mode == "running":
            self.query_one(LiveRunMonitor).push_step_only(view)

    def push_live_update(self, view: Any) -> None:
        if self._screen_mode == "running":
            self._last_live_view = view
            self.query_one(LiveRunMonitor).push_update(view)

    # ── Internal refresh coordination ──

    def _refresh(self) -> None:
        """Single refresh path — avoids state drift between CSS classes and text."""
        with self.app.batch_update():
            self._render_verdict()
            self._render_visibility()
            self._refresh_ready_surfaces()
            self._refresh_action_bar()

    def _refresh_action_bar(self) -> None:
        """Sync ActionBar + contextual button disabled states to current screen mode."""
        try:
            bar = self.query_one(ActionBar)
        except Exception:
            return
        mode = self._screen_mode
        _gating = {
            "cv-btn-run": mode != "running",
            "cv-btn-reanalyze": mode in ("ready", "stale"),
            "cv-btn-investigate": mode in ("ready", "stale"),
            "cv-btn-edit": True,
            "cv-btn-export": self.check_action_export_report(),
            "cv-btn-attribution": True,
            "cv-btn-builder": True,
            "cv-btn-back": True,
        }
        for btn_id, enabled in _gating.items():
            try:
                bar.query_one(f"#{btn_id}", Button).disabled = not enabled
            except Exception:
                pass
        # Contextual buttons — same gating
        _ctx_gating = {
            "cv-ctx-run": mode != "running",
            "cv-ctx-reanalyze": mode in ("ready", "stale"),
            "cv-ctx-edit": True,
            "cv-ctx-export": self.check_action_export_report(),
            "cv-ctx-investigate": mode in ("ready", "stale"),
            "cv-ctx-attribution": True,
            "cv-ctx-isolate": (
                mode in ("ready", "stale")
                and self._outcomes is not None
                and self._outcomes.verdict in ("regression", "mixed")
            ),
        }
        for btn_id, enabled in _ctx_gating.items():
            try:
                self.query_one(f"#{btn_id}", Button).disabled = not enabled
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        _dispatch = {
            "cv-btn-run": self.action_run_evaluation,
            "cv-btn-reanalyze": self.action_analysis_rerun,
            "cv-btn-investigate": self.action_select_episode,
            "cv-btn-edit": self.action_edit_case,
            "cv-btn-export": self.action_export_report,
            "cv-btn-attribution": self.action_open_attribution,
            "cv-btn-builder": self.action_open_builder,
            "cv-btn-back": lambda: self.app.pop_screen(),
            # Contextual buttons
            "cv-ctx-run": self.action_run_evaluation,
            "cv-ctx-reanalyze": self.action_analysis_rerun,
            "cv-ctx-edit": self.action_edit_case,
            "cv-ctx-export": self.action_export_report,
            "cv-ctx-investigate": self.action_select_episode,
            "cv-ctx-attribution": self.action_open_attribution,
            "cv-ctx-isolate": self.action_run_isolation,
        }
        handler = _dispatch.get(event.button.id or "")
        if handler:
            handler()

    def _render_verdict(self) -> None:
        block = self.query_one("#cv-verdict-block", Static)

        # Clear verdict-specific classes
        block.remove_class("cv-vb-regression", "cv-vb-improvement", "cv-vb-nochange")

        if self._screen_mode == "idle":
            block.border_title = "Verdict"
            block.update("No evaluation results yet. Press [bold]r[/bold] to run this case.\n")
            return

        if self._screen_mode == "running":
            block.border_title = "Verdict"
            text = Text()
            if self._progress_side:
                if self._progress_side == "ab":
                    text.append(f"Running parallel A/B \u2014 Episode "
                                f"{self._progress_episode}/{self._progress_total}", style="bold")
                else:
                    text.append(f"Running \u2014 Side {self._progress_side.upper()}: "
                                f"{self._progress_episode}/{self._progress_total}", style="bold")
            else:
                text.append("Running parallel A/B\u2026", style="bold")
            if self._live_view_mode != "none":
                text.append(f"  live: {self._live_view_mode}", style="dim")
            block.update(text)
            return

        if self._screen_mode == "pending":
            block.border_title = "Verdict"
            block.update("Parallel execution complete. Computing outcomes\u2026\n")
            return

        if self._screen_mode == "failed":
            block.border_title = "Verdict"
            msg = self._error_message or "Unknown error"
            block.update(f"[red]Evaluation failed[/red] \u2014 {msg.splitlines()[0]}\n")
            return

        if not self._outcomes:
            block.border_title = "Verdict"
            block.update("No results available.\n")
            return

        o = self._outcomes
        # Set border_title and class based on verdict
        if o.verdict == "regression":
            block.border_title = "REGRESSION"
            block.add_class("cv-vb-regression")
            headline = f"[bold red]{o.verdict_headline}[/bold red]"
        elif o.verdict == "improvement":
            block.border_title = "IMPROVEMENT"
            block.add_class("cv-vb-improvement")
            headline = f"[bold green]{o.verdict_headline}[/bold green]"
        elif o.verdict == "no_change":
            block.border_title = "NO CHANGE"
            block.add_class("cv-vb-nochange")
            headline = f"[dim]{o.verdict_headline}[/dim]"
        else:
            block.border_title = o.verdict.upper()
            headline = f"[bold yellow]{o.verdict_headline}[/bold yellow]"

        sig = " [bold](significant)[/bold]" if o.significant else " [dim](not significant)[/dim]"
        stale_banner = "[yellow bold]STALE[/yellow bold] \u2014 case edited since last eval.\n" if self._stale else ""

        block.update(
            f"{stale_banner}{headline}{sig}\n"
            f"{o.primary_metric_line}\n"
            f"[dim]{o.findings_count_line}[/dim]"
        )

    def _render_visibility(self) -> None:
        # Remove all mode classes
        for cls in _MODE_CSS.values():
            self.remove_class(cls)
        # Add current mode class
        self.add_class(_MODE_CSS.get(self._screen_mode, "cv-draft"))
        # Update CaseBar state
        state_map = {
            "idle": "draft",
            "running": "running",
            "pending": "pending",
            "ready": "ready",
            "stale": "ready",
            "failed": "run_failed",
        }
        try:
            self.query_one(CaseBar).update_state(state_map.get(self._screen_mode, "draft"))
        except Exception:
            pass
        # Empty state toggle
        if self._screen_mode == "idle" and self._episode_count == 0:
            self.add_class("cv-empty")
        else:
            self.remove_class("cv-empty")
        # Clear LiveRunMonitor when leaving running/pending
        if self._screen_mode not in ("running", "pending"):
            try:
                self.query_one(LiveRunMonitor).clear()
            except Exception:
                pass

    def _refresh_ready_surfaces(self) -> None:
        """Rebuild data-dependent surfaces (episode table, summary) on state change."""
        if self._screen_mode in ("ready", "stale"):
            self._rerender_episode_table()
        # Draft body
        draft = self.query_one("#cv-draft-body", Static)
        if self._screen_mode == "idle":
            draft.update("TheSean will run A and B in parallel, then compute verdict + episode ranking.")
        else:
            draft.update("")

    def _rerender_episode_table(self) -> None:
        """Clear and rebuild the episode table rows."""
        self._selected_episode_row = None
        table = self.query_one("#cv-episode-table", DataTable)
        table.clear(columns=True)
        table.zebra_stripes = True
        table.cursor_type = "row"
        table.add_columns("#", "Reward A", "Reward B", "Progress", "Divergences", "Status")
        self._populate_episode_rows(table)
        # Update wrapper border_title with record count (Harlequin pattern)
        wrapper = self.query_one("#cv-table-wrapper", Vertical)
        if table.row_count > 0:
            wrapper.border_title = f"Episodes ({table.row_count})"
        else:
            wrapper.border_title = "Episodes"

    def _populate_episode_rows(self, table: DataTable) -> None:
        if self._episode_count == 0 or self._case_state in (CaseState.DRAFT, CaseState.RUN_FAILED):
            return

        top_run_ep = None
        recommended = set()
        eps_a = []
        eps_b = []
        if self._outcomes:
            if self._outcomes.top_run:
                top_run_ep = self._outcomes.top_run.get("episode_id")
            recommended = set(self._outcomes.recommended_run_ids)
            eps_a = self._outcomes.episodes_a
            eps_b = self._outcomes.episodes_b

        for i in range(self._episode_count):
            ep_id = f"ep_{i:04d}"
            event_count = len(self._events_by_episode.get(ep_id, []))

            # Reward A / Reward B as separate columns
            reward_a_str: Text | str = ""
            reward_b_str: Text | str = ""
            if i < len(eps_a) and i < len(eps_b):
                ra, rb = eps_a[i].total_reward, eps_b[i].total_reward
                reward_a_str = Text(f"{ra:.0f}")
                reward_b_str = Text(f"{rb:.0f}")
                if rb > ra * 1.02:
                    reward_b_str.stylize("green")
                elif rb < ra * 0.98:
                    reward_b_str.stylize("red")

            # Progress A->B with directional coloring
            prog_str: Text | str = ""
            if i < len(eps_a) and i < len(eps_b):
                pa, pb = eps_a[i].final_track_progress, eps_b[i].final_track_progress
                prog_text = Text(f"{pa:.0%}\u2192{pb:.0%}")
                if pb > pa + 0.02:
                    prog_text.stylize("green")
                elif pb < pa - 0.02:
                    prog_text.stylize("red")
                prog_str = prog_text

            # Status label with Rich markup
            status: Text | str = ""
            if ep_id == top_run_ep:
                if self._outcomes and self._outcomes.verdict == "regression":
                    status = Text("\u25cf WORST", style="bold red")
                else:
                    status = Text("\u25cf TOP", style="bold green")
            elif ep_id in recommended:
                status = "\u2605"
            if i < len(eps_a) and i < len(eps_b):
                if eps_b[i].total_reward > eps_a[i].total_reward * 1.05:
                    if not status:
                        status = Text("\u2191 improved", style="green")

            table.add_row(
                str(i + 1), reward_a_str, reward_b_str,
                prog_str, str(event_count), status,
                key=str(i),
            )

    # ── Actions ──

    def check_action_select_episode(self) -> bool:
        return self._screen_mode in ("ready", "stale")

    def action_select_episode(self) -> None:
        table = self.query_one("#cv-episode-table", DataTable)
        if table.row_count == 0:
            return
        row_key = table.cursor_row
        if row_key is None:
            return
        # Toggle: if same row is already selected, deselect
        if self._selected_episode_row == row_key:
            self._selected_episode_row = None
            table.cursor_type = "none"
            table.cursor_type = "row"
            return
        self._selected_episode_row = row_key
        key = table.get_row_at(row_key)
        episode_idx = int(key[0]) - 1
        self.post_message(self.EpisodeSelected(episode_idx))

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
            self.app._open_attribution()

    def action_run_isolation(self) -> None:
        if hasattr(self.app, "run_isolation"):
            self.app.run_isolation()

    def action_open_builder(self) -> None:
        if hasattr(self.app, "_open_run_builder"):
            self.app._open_run_builder()

    def action_export_report(self) -> None:
        app = self.app
        if hasattr(app, "export_report"):
            app.export_report()

    def check_action_export_report(self) -> bool:
        app = self.app
        ws = getattr(getattr(app, "state", None), "current_workspace", None)
        if not ws:
            return False
        result_path = ws / "analysis" / "result.json"
        return bool(result_path.exists())
