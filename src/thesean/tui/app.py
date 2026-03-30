"""TheSeanApp — case-based investigation workspace."""

from __future__ import annotations

import queue as _queue_mod
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static
from textual.worker import Worker

from thesean.pipeline.live_update import LivePairFrame
from thesean.pipeline.paired_runner import EvalCancelled as _EvalCancelled
from thesean.pipeline.state import StageResult
from thesean.pipeline.workspace import ERR_ANALYSIS, save_failed_attempt, update_case_state
from thesean.tui.actions import TheSeanActions
from thesean.tui.detection import (
    detect_context,
    load_recent_cases,
    save_recent_case,
)
from thesean.tui.services import TuiBackendService
from thesean.tui.state import AppState, CaseState, RuntimeStatus, ScreenMode

if TYPE_CHECKING:
    from thesean.tui.screens.run_builder import RunBuilderScreen


def _fallback_pair_view(frame: LivePairFrame) -> "LivePairTelemetryView":  # type: ignore[name-defined]  # noqa: F821
    """Minimal pair view when no adapter is available."""
    from thesean.core.signal_schema import LivePairTelemetryView

    rows_a: list[tuple[str, str]] = []
    rows_b: list[tuple[str, str]] = []
    compare: list[tuple[str, str]] = []
    prog_a = frame.a.progress if frame.a else 0.0
    prog_b = frame.b.progress if frame.b else 0.0

    if frame.a:
        rows_a = [("Progress:", f"{prog_a:.1%}"), ("Step:", str(frame.a.step))]
    if frame.b:
        rows_b = [("Progress:", f"{prog_b:.1%}"), ("Step:", str(frame.b.step))]
    if frame.a and frame.b:
        delta = prog_b - prog_a
        sign = "+" if delta >= 0 else ""
        compare = [("Δ Progress:", f"{sign}{delta:.1%}")]

    action_a = list(frame.a.action) if frame.a and frame.a.action else []
    action_b = list(frame.b.action) if frame.b and frame.b.action else []

    return LivePairTelemetryView(
        episode=frame.episode_idx + 1, episode_total=frame.episode_total,
        tick=frame.tick, rows_a=rows_a, rows_b=rows_b, compare_rows=compare,
        action_a=action_a, action_b=action_b,
        done_a=frame.a.done if frame.a else False,
        done_b=frame.b.done if frame.b else False,
        term_a=frame.a.termination if frame.a else None,
        term_b=frame.b.termination if frame.b else None,
        progress_a=prog_a, progress_b=prog_b,
        max_ticks=frame.max_steps,
    )


class TuiStageObserver:
    """Bridges pipeline StageObserver calls to TUI updates via call_from_thread."""

    def __init__(self, app: TheSeanApp) -> None:
        self.app = app

    def on_stage_start(self, name: str) -> None:
        self.app._safe_call(self.app._update_run_monitor, name, "running")

    def on_stage_complete(self, name: str, result: StageResult) -> None:
        self.app._safe_call(self.app._update_run_monitor, name, "completed")

    def on_stage_fail(self, name: str, error: str) -> None:
        self.app._safe_call(self.app._update_run_monitor, name, "failed", error)

    def on_stage_skip(self, name: str, reason: str) -> None:
        self.app._safe_call(self.app._update_run_monitor, name, "skipped")

    def on_stage_reuse(self, name: str) -> None:
        self.app._safe_call(self.app._update_run_monitor, name, "completed")


def _queue_put_newest(q: _queue_mod.Queue, item: object) -> None:
    """Put item into queue, dropping oldest if full. Freshness over completeness."""
    try:
        q.put_nowait(item)
    except _queue_mod.Full:
        try:
            q.get_nowait()
        except _queue_mod.Empty:
            pass
        try:
            q.put_nowait(item)
        except _queue_mod.Full:
            pass


class TheSeanApp(App):
    CSS_PATH = "styles/app.tcss"

    TITLE = "TheSean"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("r", "run_investigation", "Run", show=True),
        Binding("c", "run_compare", "Compare", show=True),
        Binding("slash", "open_command_palette", "Cmd palette", show=True),
        Binding("question_mark", "open_help", "Help", show=True),
        Binding("b", "push_builder", "Builder", show=True),
        Binding("i", "push_investigation", "Investigation", show=True),
        Binding("a", "push_attribution", "Attribution", show=True),
    ]

    def __init__(self, explicit_workspace: Path | None = None) -> None:
        super().__init__(watch_css=True)

        from textual.theme import Theme

        thesean_theme = Theme(
            name="thesean",
            primary="#BD93F9",       # Dracula purple — focus borders, primary accent
            secondary="#50FA7B",     # Dracula green — success, improvement
            warning="#F1FA8C",       # Dracula yellow — warnings, in-progress
            error="#FF5555",         # Dracula red — regression, errors
            accent="#FF79C6",        # Dracula pink — accent highlights
            foreground="#F8F8F2",    # Dracula foreground
            background="#282A36",    # Dracula background
            surface="#282A36",       # same as bg (flat feel)
            panel="#6272A4",         # Dracula comment — inactive borders
            dark=True,
        )
        self.register_theme(thesean_theme)
        self.theme = "thesean"

        self.state = AppState()
        self.backend = TuiBackendService()
        self.actions_handler = TheSeanActions(self, self.backend)
        self._explicit_workspace = explicit_workspace
        # Live monitoring state (4B)
        self._live_queue: _queue_mod.Queue | None = None
        self._live_poll_timer: object | None = None
        self._live_sidecar: object | None = None
        # Cancel flag for running evaluation
        self._eval_cancel: threading.Event = threading.Event()
        self._eval_worker: Worker | None = None
        # Set during shutdown to prevent call_from_thread crashes
        self._shutting_down: bool = False

    def _safe_call(self, callback: object, *args: object, **kwargs: object) -> None:
        """call_from_thread that silently no-ops if the app is shutting down."""
        if self._shutting_down:
            return
        try:
            self.call_from_thread(callback, *args, **kwargs)  # type: ignore[arg-type]
        except Exception:
            pass  # App message loop already closed

    def compose(self) -> ComposeResult:
        yield Footer()

    def action_quit(self) -> None:  # type: ignore[override]
        """Cancel running eval worker before exit to avoid SIGSEGV in torch/numpy."""
        self._shutting_down = True
        self._eval_cancel.set()
        self._stop_live_monitoring()
        worker = self._eval_worker
        if worker is not None and worker.is_running:
            import asyncio

            async def _wait_and_exit() -> None:
                try:
                    await asyncio.wait_for(worker.wait(), timeout=3.0)
                except (asyncio.TimeoutError, Exception):
                    pass
                self.exit()

            self.run_worker(_wait_and_exit, thread=False)  # type: ignore[arg-type]
        else:
            self.exit()

    def action_pop_screen(self) -> None:  # type: ignore[override]
        """Guard against popping back to the bare base screen."""
        if len(self.screen_stack) > 2:
            self.pop_screen()

    def on_mount(self) -> None:
        self.title = "TheSean"

        # Detect context from cwd
        ctx = detect_context(Path.cwd(), explicit_workspace=self._explicit_workspace)
        self.state.detected_context = ctx
        # If an explicit workspace was passed, load it directly; otherwise open Run Builder
        if ctx.case:
            self.load_workspace(ctx.case)
        else:
            self._open_run_builder()

    # ── Workspace loading ──

    def load_workspace(self, workspace: Path) -> None:
        workspace = workspace.expanduser().resolve()
        if not workspace.exists():
            self.show_error("Workspace not found", f"Path does not exist: {workspace}")
            return
        self.state.current_workspace = workspace
        self.state.case_name = workspace.name
        self.state.runtime = RuntimeStatus(mode="loading_case", message="Loading...")
        self.notify(f"Loading case: {workspace.name}...")
        self.run_worker(self._load_workspace_worker, thread=True)

    def _load_workspace_worker(self) -> None:
        ws = self.state.current_workspace
        if ws is None:
            return
        try:
            bundle = self.backend.load_workspace_bundle(ws)
            self._safe_call(self._apply_workspace_data, bundle)
        except FileNotFoundError:
            # Pre-run workspace — load case only and open in ready mode
            self._safe_call(self._apply_pre_run_state)
        except Exception as e:
            self._safe_call(self._on_load_failed, str(e))

    def _on_load_failed(self, error: str) -> None:
        self.state.runtime = RuntimeStatus(mode="error", error=error)
        self.show_error("Failed to load workspace", error)

    def _apply_pre_run_state(self) -> None:
        """Handle pre-run workspace — load case without pipeline results."""
        ws = self.state.current_workspace
        if ws is None:
            return
        self.state.case = self.backend.load_case(ws)
        self.state.workspace_loaded = True
        self.state.runtime = RuntimeStatus(mode="idle")
        self.state.events = []

        # Load outcomes if available (D-18: fast reopen)
        if ws:
            self.state.outcomes = self.backend.load_outcomes(ws)

        # Set case_state and live_view from workspace_state.json
        if ws:
            ws_state = self.backend.load_workspace_state(ws)
            raw_state = ws_state.get("case_state", "draft")
            try:
                self.state.case_state = CaseState(raw_state)
            except ValueError:
                self.state.case_state = CaseState.DRAFT
            live_view = ws_state.get("live_view", "tui")
            if live_view in ("none", "tui", "sidecar", "both"):
                self.state.live_view = live_view

        # Resolve signal translator (Phase 7)
        self._resolve_translator()
        self._load_track_geometry()

        if ws:
            save_recent_case(self.state.detected_context.project_root, ws)

        self.notify("Case loaded (pipeline not run yet). Press r to run.")
        self._open_case_verdict()

    def _apply_workspace_data(self, bundle: object) -> None:
        from thesean.reporting.types import ReportBundle

        if not isinstance(bundle, ReportBundle):
            return

        ws = self.state.current_workspace

        self.state.report_bundle = bundle
        self.state.compare_report = bundle.compare
        self.state.isolation_bundle = bundle.isolation
        self.state.attributions = list(bundle.attribution)
        self.state.workspace_loaded = True
        self.state.runtime = RuntimeStatus(mode="idle")

        # Save to recent cases
        if ws:
            save_recent_case(self.state.detected_context.project_root, ws)

        # Load events if available
        if ws:
            self.state.events = self.backend.load_events(ws)

        # Load case if available
        if ws:
            self.state.case = self.backend.load_case(ws)

        # Load outcomes if available (D-18: fast reopen)
        if ws:
            self.state.outcomes = self.backend.load_outcomes(ws)

        # Set case_state from workspace_state.json (Task 7.11 bug fix)
        if ws:
            ws_state = self.backend.load_workspace_state(ws)
            raw_state = ws_state.get("case_state", "draft")
            try:
                self.state.case_state = CaseState(raw_state)
            except ValueError:
                self.state.case_state = CaseState.DRAFT
            live_view = ws_state.get("live_view", "tui")
            if live_view in ("none", "tui", "sidecar", "both"):
                self.state.live_view = live_view

        # Resolve signal translator (Phase 7)
        self._resolve_translator()
        self._load_track_geometry()

        # Push CaseVerdict screen as primary view
        self._open_case_verdict()

    def _resolve_translator(self) -> None:
        """Resolve signal translator from adapter factory (Phase 7)."""
        ctx = self.state.detected_context
        if ctx.adapter and ctx.project_root:
            try:
                from thesean.cli.wizard.discovery import load_factory
                factory = load_factory(ctx.adapter)
                factory.bind_repo(ctx.project_root)
                if hasattr(factory, "get_signal_translator"):
                    translator = factory.get_signal_translator()
                    self.state.signal_translator = translator
                    if translator and hasattr(translator, "signal_schema"):
                        self.state.signal_schema = translator.signal_schema()
            except Exception:
                pass

    def _load_track_geometry(self) -> None:
        """Load track centerline geometry for braille track map rendering."""
        ctx = self.state.detected_context
        case = self.state.case
        if not case or not ctx.project_root:
            return
        track_ref = getattr(case, "track_ref", None)
        if not track_ref:
            return
        track_csv = ctx.project_root / "tracks" / f"{track_ref}.csv"
        if not track_csv.exists():
            return
        try:
            import csv
            points: list[tuple[float, float]] = []
            with open(track_csv) as f:
                for row in csv.reader(f):
                    if not row or row[0].strip().startswith("#"):
                        continue
                    try:
                        points.append((float(row[0].strip()), float(row[1].strip())))
                    except (ValueError, IndexError):
                        continue
            if points:
                self.state.track_geometry = points
        except Exception:
            pass

    def refresh_bundle(self) -> None:
        if self.state.current_workspace:
            self.load_workspace(self.state.current_workspace)

    # ── Pipeline execution ──

    def run_pipeline_action(
        self,
        compare_only: bool = False,
        report_only: bool = False,
        isolate_only: bool = False,
    ) -> None:
        if self.state.current_workspace is None:
            self.show_error("No workspace", "Open a workspace first.")
            return

        if compare_only:
            self.state.runtime = RuntimeStatus(mode="running_compare")
        elif report_only:
            self.state.runtime = RuntimeStatus(mode="running_report")
        elif isolate_only:
            self.state.runtime = RuntimeStatus(mode="running_isolate")
        else:
            self.state.runtime = RuntimeStatus(mode="running_compare")
        if compare_only:
            self.run_worker(lambda: self._run_pipeline_worker(compare_only=True), thread=True)
        elif report_only:
            self.run_worker(lambda: self._run_pipeline_worker(report_only=True), thread=True)
        elif isolate_only:
            self.run_worker(lambda: self._run_pipeline_worker(isolate_only=True), thread=True)
        else:
            self.run_worker(lambda: self._run_pipeline_worker(), thread=True)

    def _run_pipeline_worker(
        self,
        compare_only: bool = False,
        report_only: bool = False,
        isolate_only: bool = False,
    ) -> None:
        ws = self.state.current_workspace
        if ws is None:
            return
        observer = TuiStageObserver(self)
        try:
            if compare_only:
                self.backend.run_compare_only(ws, observer=observer)
            elif report_only:
                self.backend.run_report_only(ws, observer=observer)
            elif isolate_only:
                self.backend.run_isolate_only(ws, observer=observer)
            else:
                self.backend.run_full_pipeline(ws, observer=observer)
            self._safe_call(self._on_pipeline_complete)
        except Exception as e:
            self._safe_call(self._on_pipeline_failed, str(e))

    def _on_pipeline_complete(self) -> None:
        self.state.runtime = RuntimeStatus(mode="idle")
        self.refresh_bundle()

    def _on_pipeline_failed(self, error: str) -> None:
        self.state.runtime = RuntimeStatus(mode="error", error=error)
        self.show_error("Pipeline failed", error)

    def _update_run_monitor(self, name: str, status: str, error: str = "") -> None:
        if status == "running":
            mode_map = {
                "compare": "running_compare",
                "isolate": "running_isolate",
                "attribute": "running_attribute",
                "report": "running_report",
            }
            mode = mode_map.get(name, "running_compare")
            self.state.runtime = RuntimeStatus(mode=mode, current_stage=name)  # type: ignore[arg-type]
        elif status == "failed":
            self.state.runtime = RuntimeStatus(mode="error", current_stage=name, error=error)
        elif status in ("completed", "skipped"):
            self.state.runtime.current_stage = name

    # ── Isolation trigger ──

    _isolate_confirm_pending: bool = False

    def run_isolation(self) -> None:
        """Run swap-test isolation pipeline. Requires regression verdict."""
        ws = self.state.current_workspace
        if not ws:
            self.notify("No workspace loaded.", severity="warning")
            return
        if self.state.runtime.mode not in ("idle", "error"):
            self.notify("Pipeline already running.", severity="warning")
            return
        outcomes = self.state.outcomes
        if not outcomes or outcomes.verdict not in ("regression", "mixed"):
            self.notify("Isolation requires a regression or mixed verdict.", severity="warning")
            return
        # Confirmation gate: first press warns, second press runs
        if not self._isolate_confirm_pending:
            ep_count = getattr(self.state.case, "episode_count", 5) if self.state.case else 5
            self.notify(
                f"Isolation will run 6 swap tests x {ep_count} episodes. "
                f"Press I again to confirm."
            )
            self._isolate_confirm_pending = True
            return
        self._isolate_confirm_pending = False
        self.notify("Starting isolation pipeline...")
        self.run_pipeline_action(isolate_only=True)

    # ── Screen notification dispatchers ──

    def _notify_screen_running(self) -> None:
        screen = self.screen
        if hasattr(screen, "set_running"):
            from thesean.tui.screens.case_verdict import CaseVerdictScreen
            if isinstance(screen, CaseVerdictScreen):
                # Pygame sidecar disabled — always report as disabled
                screen.set_running(sidecar_status="disabled", live_view=self.state.live_view)
            else:
                screen.set_running()
        else:
            from thesean.tui.screens.investigation import InvestigationScreen
            if isinstance(screen, InvestigationScreen):
                screen.query_one("#inv-status-line", Static).update("running…")

    def _notify_screen_progress(self, side: str, episode: int, total: int) -> None:
        screen = self.screen
        if hasattr(screen, "set_progress"):
            screen.set_progress(side=side, episode=episode, total=total)
        else:
            from thesean.tui.screens.investigation import InvestigationScreen
            if isinstance(screen, InvestigationScreen):
                screen.update_progress(side, episode, total)

    def _notify_screen_pending(self) -> None:
        screen = self.screen
        if hasattr(screen, "set_pending"):
            screen.set_pending()
        else:
            from thesean.tui.screens.investigation import InvestigationScreen
            if isinstance(screen, InvestigationScreen):
                screen.query_one("#inv-status-line", Static).update("computing outcomes…")

    def _notify_screen_failed(self, error: str) -> None:
        screen = self.screen
        if hasattr(screen, "set_failed"):
            screen.set_failed(error)

    def _notify_screen_ready(self, outcomes: object) -> None:
        screen = self.screen
        if hasattr(screen, "set_ready"):
            ws = self.state.current_workspace
            episode_count = self.backend.get_episode_count(ws, "a") if ws else 0
            events_by_episode = self.backend.load_events_by_episode(ws) if ws else {}
            screen.set_ready(outcomes, episode_count, events_by_episode)

    # ── Evaluation execution (D-19) ──

    def run_analysis_only(self) -> None:
        """Re-derive outcomes from existing episode data without re-running evaluation (EVAL-01, EVAL-02).

        Guards: workspace must exist, at least one side's episodes.json must exist.
        Reuses _run_analysis_worker which calls backend.run_analysis().
        """
        ws = self.state.current_workspace
        if not ws:
            self.notify("No workspace loaded.", severity="warning")
            return

        # Guard: at least side A episodes must exist
        episodes_a = ws / "runs" / "a" / "episodes.json"
        if not episodes_a.exists():
            self.notify("No episode data found. Run full evaluation first.", severity="warning")
            return

        self._notify_screen_pending()

        self.notify("Re-analyzing from existing episode data...")
        self.run_worker(self._run_analysis_worker, thread=True)

    def run_evaluation(self) -> None:
        """Start evaluation in a worker thread (D-19)."""
        import torch  # noqa: F401 — pre-init on main thread to avoid SIGSEGV in worker

        if self.state.case_state == CaseState.RUNNING:
            self.notify("Evaluation already in progress.")
            return

        self._eval_cancel.clear()
        self.state.case_state = CaseState.RUNNING
        self.state.runtime.mode = "eval_running_a"
        self.state.runtime.eval_episode = 0
        self.state.runtime.eval_total = self.state.case.episode_count if self.state.case else 0

        self._notify_screen_running()

        if self.state.current_workspace:
            update_case_state(self.state.current_workspace, "running")

        try:
            # Set running state on InvestigationScreen (4B: show LiveRunMonitor)
            from thesean.tui.screens.investigation import InvestigationScreen
            if isinstance(self.screen, InvestigationScreen):
                self.screen.set_screen_mode(ScreenMode.RUNNING_LIVE)

            # Start live poll timer if TUI monitoring is active
            if self.state.live_view in ("tui", "both"):
                self._live_poll_timer = self.set_interval(0.05, self._poll_live_queue)

            self._eval_worker = self.run_worker(self._run_eval_worker, thread=True)
        except Exception as exc:
            self._on_eval_error(str(exc))

    def _run_eval_worker(self) -> None:
        """Worker thread: run evaluation and save episodes."""
        import traceback

        workspace = self.state.current_workspace
        case = self.state.case
        ctx = self.state.detected_context

        if not workspace or not case or not ctx.adapter or not ctx.project_root:
            self._safe_call(self._on_eval_error, "Missing workspace or adapter context")
            return

        live_view = self.state.live_view

        # TUI queue (for TUI consumer) — carries LivePairFrame (4C)
        tui_queue: _queue_mod.Queue | None = None
        if live_view in ("tui", "both"):
            tui_queue = _queue_mod.Queue(maxsize=200)
            self._live_queue = tui_queue

        # Pygame sidecar — disabled, buggy on macOS Apple Silicon (segfaults
        # during SDL2 joystick teardown). Kept for future development.
        # if live_view in ("sidecar", "both"):
        #     sidecar = self._start_sidecar_if_possible(case, ctx)
        #     if sidecar is not None:
        #         self._live_sidecar = sidecar

        # Build live_sink that fans out to active consumers (4C: receives LivePairFrame)
        def live_sink(frame: LivePairFrame) -> None:
            if tui_queue is not None:
                _queue_put_newest(tui_queue, frame)

        has_sink = tui_queue is not None

        def progress_cb(side: str, ep: int, total: int) -> None:
            mode = "eval_running_a" if side == "a" else f"eval_running_{side}"
            self._safe_call(self._update_eval_progress, mode, ep, total)
            # Also notify screen with paired progress
            self._safe_call(self._notify_screen_progress, side, ep, total)

        try:
            self.backend.run_evaluation(
                workspace, case, ctx.adapter, ctx.project_root,
                progress_callback=progress_cb,
                live_sink=live_sink if has_sink else None,
                cancel_event=self._eval_cancel,
            )
            self._safe_call(self._on_eval_complete)
        except _EvalCancelled:
            self._safe_call(self._on_eval_cancelled)
            return
        except Exception as e:
            if self._shutting_down:
                return
            tb = traceback.format_exc()
            # Save failure metadata (D-08)
            try:
                save_failed_attempt(
                    workspace,
                    side=None, episode=None, step=None,
                    error_category="execution",
                    error_message=str(e),
                    stack_trace=tb,
                )
            except Exception:
                pass  # Don't let failure recording crash the error handler
            self._safe_call(self._on_eval_error, str(e))

    def _update_eval_progress(self, mode: str, episode: int, total: int) -> None:
        self.state.runtime.mode = mode  # type: ignore[assignment]
        self.state.runtime.eval_episode = episode
        self.state.runtime.eval_total = total

        side = mode.replace("eval_running_", "")
        self._notify_screen_progress(side, episode, total)

    def _on_eval_complete(self) -> None:
        """Episodes saved. Transition to ANALYSIS_PENDING and run analysis in a worker."""
        self._eval_worker = None
        self._stop_live_monitoring()
        self.state.runtime.mode = "eval_computing"
        self._notify_screen_pending()
        self.run_worker(self._run_analysis_worker, thread=True)

    def _run_analysis_worker(self) -> None:
        """Worker thread: compute outcomes from saved episodes (D-15, D-16, D-17)."""
        import traceback

        workspace = self.state.current_workspace
        if not workspace:
            self._safe_call(self._on_analysis_error, "No workspace")
            return

        try:
            outcomes = self.backend.run_analysis(workspace, translator=self.state.signal_translator)
            self._safe_call(self._on_analysis_complete, outcomes)
        except Exception as e:
            if self._shutting_down:
                return
            tb = traceback.format_exc()
            try:
                save_failed_attempt(
                    workspace,
                    side=None, episode=None, step=None,
                    error_category=ERR_ANALYSIS,
                    error_message=str(e),
                    stack_trace=tb,
                )
            except Exception:
                pass
            self._safe_call(self._on_analysis_error, str(e))

    def _on_analysis_complete(self, outcomes: object) -> None:
        """Outcomes computed. Set state to READY and update screen in-place or re-push."""
        from thesean.models.episode import OutcomeSummary
        if isinstance(outcomes, OutcomeSummary):
            self.state.outcomes = outcomes
        self.state.case_state = CaseState.READY
        self.state.runtime.mode = "complete"
        self.state.runtime.eval_episode = 0
        self.state.runtime.eval_total = 0
        if self.state.current_workspace:
            update_case_state(self.state.current_workspace, "ready")
            # Reload attributions from stage_outputs written by run_analysis
            self.state.attributions = self.backend.load_attributions(
                self.state.current_workspace
            )
            self.state.events = self.backend.load_events(
                self.state.current_workspace
            )
        self.notify("Evaluation complete. Outcomes computed.")
        from thesean.tui.screens.case_verdict import CaseVerdictScreen
        from thesean.tui.screens.investigation import InvestigationScreen
        if isinstance(self.screen, CaseVerdictScreen):
            self._notify_screen_ready(outcomes)
        elif isinstance(self.screen, InvestigationScreen):
            self.screen.set_screen_mode(ScreenMode.READY_INVESTIGATION)
            self.pop_screen()
            self._open_case_verdict()
        else:
            self._open_case_verdict()

    def _on_analysis_error(self, error_msg: str) -> None:
        """Analysis failed after a successful run (D-17). Keep raw runs, set analysis_partial."""
        self.state.case_state = CaseState.ANALYSIS_PARTIAL
        self.state.runtime.mode = "error"
        self.state.runtime.error = error_msg
        if self.state.current_workspace:
            update_case_state(self.state.current_workspace, "analysis_partial")
        msg = f"Outcome computation failed: {error_msg}. Run data preserved — press r to retry."
        self.notify(msg, severity="warning")
        from thesean.tui.screens.case_verdict import CaseVerdictScreen
        from thesean.tui.screens.investigation import InvestigationScreen
        if isinstance(self.screen, CaseVerdictScreen):
            self._notify_screen_failed(error_msg)
        elif isinstance(self.screen, InvestigationScreen):
            self.screen.set_screen_mode(ScreenMode.ANALYSIS_FAILED)
            self.pop_screen()
            self._open_case_verdict()
        else:
            self._open_case_verdict()

    def _on_eval_error(self, error_msg: str) -> None:
        self._eval_worker = None
        self._stop_live_monitoring()
        self.state.case_state = CaseState.RUN_FAILED
        self.state.runtime.mode = "error"
        self.state.runtime.error = error_msg
        self.state.outcomes = None  # Clear stale outcomes from previous run
        # Notify active screen
        from thesean.tui.screens.investigation import InvestigationScreen
        if isinstance(self.screen, InvestigationScreen):
            self.screen.set_screen_mode(ScreenMode.DRAFT_EMPTY)
        else:
            self._notify_screen_failed(error_msg)
        self.notify(f"Evaluation failed: {error_msg}. Workspace preserved -- check error log.", severity="error")
        # Persist state (D-05: never eject user)
        if self.state.current_workspace:
            update_case_state(self.state.current_workspace, "run_failed")

    def cancel_evaluation(self) -> None:
        """Signal the running evaluation to stop."""
        if self.state.case_state != CaseState.RUNNING:
            return
        self._eval_cancel.set()
        self.notify("Cancelling evaluation...")

    def _on_eval_cancelled(self) -> None:
        """Handle a cleanly-cancelled evaluation."""
        self._eval_worker = None
        self._stop_live_monitoring()
        self.state.case_state = CaseState.RUN_FAILED
        self.state.runtime.mode = "idle"
        self.state.runtime.error = None
        self.state.outcomes = None
        if self.state.current_workspace:
            update_case_state(self.state.current_workspace, "run_failed")
        self.notify("Evaluation cancelled.")
        from thesean.tui.screens.investigation import InvestigationScreen
        if isinstance(self.screen, InvestigationScreen):
            self.screen.set_screen_mode(ScreenMode.DRAFT_EMPTY)

    # ── Live monitoring (4B) ──

    def _poll_live_queue(self) -> None:
        """Drain queue, log every step, update dashboard with latest only."""
        q = self._live_queue
        if q is None:
            return
        frames: list[object] = []
        while True:
            try:
                frames.append(q.get_nowait())
            except _queue_mod.Empty:
                break
        if not frames:
            return
        # Log step lines for all intermediate frames
        for raw in frames[:-1]:
            self._push_live_update(raw, step_only=True)
        # Full dashboard update for the latest frame
        self._push_live_update(frames[-1], step_only=False)

    def _push_live_update(self, raw: object, *, step_only: bool = False) -> None:
        """Transform LivePairFrame via adapter, forward to active screen."""

        if not isinstance(raw, LivePairFrame):
            return

        frame: LivePairFrame = raw

        # Try adapter formatting
        translator = getattr(self.state, "signal_translator", None)
        if translator and hasattr(translator, "format_live_pair"):
            try:
                view = translator.format_live_pair(frame)
            except Exception:
                view = _fallback_pair_view(frame)
        else:
            view = _fallback_pair_view(frame)

        screen = self.screen
        if step_only and hasattr(screen, "push_live_step_only"):
            screen.push_live_step_only(view)
        elif hasattr(screen, "push_live_update"):
            screen.push_live_update(view)

    def _stop_live_monitoring(self) -> None:
        """Clean up live monitoring resources."""
        timer = self._live_poll_timer
        if timer is not None:
            timer.stop()  # type: ignore[attr-defined]
        self._live_poll_timer = None
        self._live_queue = None
        self._live_sidecar = None

    # Pygame sidecar — disabled, buggy on macOS Apple Silicon (segfaults
    # during SDL2 joystick teardown). Kept for future development.
    # def _start_sidecar_if_possible(self, case, ctx):
    #     from thesean.adapters.f1.live_viewer import LiveF1ViewerProcess
    #     ...

    # ── Report export (COMP-03, COMP-04) ──

    def export_report(self) -> None:
        """Export HTML report from saved artifacts (COMP-03, COMP-04)."""
        ws = self.state.current_workspace
        if not ws:
            self.notify("No workspace loaded.", severity="warning")
            return
        result_path = ws / "analysis" / "result.json"
        if not result_path.exists():
            self.notify("No saved results found. Run evaluation first.", severity="warning")
            return
        self.notify("Generating report...")
        self.run_worker(self._export_report_worker, thread=True)

    def _export_report_worker(self) -> None:
        """Worker thread: generate report file."""
        ws = self.state.current_workspace
        if not ws:
            return
        try:
            path = self.backend.generate_report_from_artifacts(ws)
            self._safe_call(self.notify, f"Report saved: {path}")
        except Exception as e:
            self._safe_call(self.notify, f"Export failed: {e}", severity="error")

    # ── Error handling ──

    def show_error(self, title: str, message: str) -> None:
        from thesean.tui.screens.error_modal import ErrorModal

        self.push_screen(ErrorModal(title, message))

    # ── Action handlers ──

    def action_run_investigation(self) -> None:
        self.actions_handler.run_investigation()

    def action_run_compare(self) -> None:
        self.actions_handler.run_compare()

    def action_open_command_palette(self) -> None:
        from thesean.tui.screens.command_palette import CommandPaletteModal

        self.push_screen(CommandPaletteModal(), callback=self._on_command_selected)

    def _on_command_selected(self, cmd: str | None) -> None:
        if cmd is None:
            return
        if cmd == "new_investigation":
            self.actions_handler.new_investigation()
        elif cmd == "open_workspace":
            self.actions_handler.open_workspace_picker()
        elif cmd == "switch_case":
            self.actions_handler.switch_case()
        elif cmd == "run_full":
            self.actions_handler.run_investigation()
        elif cmd == "run_compare":
            self.actions_handler.run_compare()
        elif cmd == "rerender_report":
            self.actions_handler.rerender_report()
        elif cmd == "screen_builder":
            self._open_run_builder()
        elif cmd == "screen_investigation":
            self._open_case_verdict()
        elif cmd == "screen_attribution":
            self._open_attribution()

    def action_open_help(self) -> None:
        self.notify(
            "Keyboard shortcuts:\n"
            "b=Builder  i=Investigation  a=Attribution\n"
            "r=Run  c=Compare  /=Cmd palette  ?=Help\n"
            "j/k=Events  h/l=Steps  e=Evidence",
            title="Help",
        )

    # ── New screen-stack navigation ──

    def action_push_builder(self) -> None:
        """Push the Run Builder screen."""
        self._open_run_builder()

    def action_push_investigation(self) -> None:
        """Push the CaseVerdict screen with current state."""
        self._open_case_verdict()

    def action_push_attribution(self) -> None:
        """Push the Attribution screen with current state."""
        self._open_attribution()

    def _open_run_builder(self) -> None:
        import contextlib

        from thesean.tui.screens.run_builder import RunBuilderScreen

        ctx = self.state.detected_context
        weights: list[dict] = []
        envs: list[str] = []
        if ctx.adapter and ctx.project_root:
            with contextlib.suppress(Exception):
                weights = self.backend.discover_weights(ctx.adapter, ctx.project_root)
            with contextlib.suppress(Exception):
                envs = self.backend.discover_envs(ctx.adapter, ctx.project_root)

        cases = list(ctx.cases)
        for r in load_recent_cases():
            if r.project:
                p = Path(r.project) / ".thesean" / "cases" / r.case
                if p.is_dir() and p not in cases:
                    cases.append(p)

        screen = RunBuilderScreen(
            weights=weights,
            envs=envs,
            project_root=ctx.project_root,
            adapter_name=ctx.adapter,
            cases=cases,
        )
        self.push_screen(screen)

    def _open_run_builder_edit(self) -> None:
        """Open RunBuilderScreen pre-populated with current case for editing (WORK-01)."""
        import contextlib

        from thesean.tui.screens.run_builder import RunBuilderScreen

        if not self.state.case or not self.state.current_workspace:
            self.notify("No case loaded to edit.", severity="warning")
            return

        ctx = self.state.detected_context
        weights: list[dict] = []
        envs: list[str] = []
        if ctx.adapter and ctx.project_root:
            with contextlib.suppress(Exception):
                weights = self.backend.discover_weights(ctx.adapter, ctx.project_root)
            with contextlib.suppress(Exception):
                envs = self.backend.discover_envs(ctx.adapter, ctx.project_root)

        cases = list(ctx.cases)

        screen = RunBuilderScreen(
            weights=weights,
            envs=envs,
            project_root=ctx.project_root,
            adapter_name=ctx.adapter,
            cases=cases,
            edit_case=self.state.case,
            edit_workspace=self.state.current_workspace,
        )
        self.push_screen(screen)

    def _open_case_verdict(self) -> None:
        """Push CaseVerdictScreen — case-level verdict with episode drill-down."""
        from thesean.tui.screens.case_verdict import CaseVerdictScreen

        ws = self.state.current_workspace
        if not ws:
            return

        episode_count = self.backend.get_episode_count(ws, "a")
        events_by_episode = self.backend.load_events_by_episode(ws)

        # Staleness check
        stale = False
        if self.state.case and self.state.outcomes:
            result = self.backend.load_result(ws)
            if result:
                from thesean.pipeline.staleness import is_result_stale
                stale = is_result_stale(self.state.case, result)

        screen = CaseVerdictScreen(
            case=self.state.case,
            case_state=self.state.case_state,
            outcomes=self.state.outcomes,
            episode_count=episode_count,
            events_by_episode=events_by_episode,
            stale=stale,
            track_geometry=self.state.track_geometry,
        )
        self.push_screen(screen)

    def on_case_verdict_screen_episode_selected(self, event: object) -> None:
        """Drill down from CaseVerdictScreen into per-episode InvestigationScreen."""
        episode_idx = getattr(event, "episode_idx", 0)
        self._open_investigation(episode_idx)

    def _open_investigation(self, episode_idx: int = 0) -> None:
        from thesean.tui.screens.investigation import InvestigationScreen

        ws = self.state.current_workspace
        if not ws:
            return

        episode_count = self.backend.get_episode_count(ws, "a")
        self.state.selected_episode_idx = episode_idx
        self.state.episode_count = episode_count
        self.state.selected_run_id = f"ep_{episode_idx:04d}"

        # Load per-step signals for selected episode
        translator = self.state.signal_translator
        signals_a = self.backend.load_episode_signals(ws, "a", episode_idx, translator=translator)
        signals_b = self.backend.load_episode_signals(ws, "b", episode_idx, translator=translator)

        # Build values for the default signal (first signal = steering)
        signal_names = translator.signal_names() if translator else []
        default_signal = signal_names[0] if signal_names else "steering"
        values_a_list: list[float] = [signals_a.get(s, {}).get(default_signal, 0.0) for s in sorted(signals_a.keys())]
        values_b_list: list[float] = [signals_b.get(s, {}).get(default_signal, 0.0) for s in sorted(signals_b.keys())]

        # Load events for this episode
        ep_id = f"ep_{episode_idx:04d}"
        events = self.backend.load_events(ws, episode_id=ep_id)
        self.state.events = events

        # Compute max_step from signal data
        max_step_a = max(signals_a.keys(), default=0)
        max_step_b = max(signals_b.keys(), default=0)
        max_step = max(max_step_a, max_step_b)

        # Divergence scores from first signal
        min_len = min(len(values_a_list), len(values_b_list))
        divergence_scores = [abs(values_a_list[i] - values_b_list[i]) for i in range(min_len)]

        # Staleness check
        stale = False
        if self.state.case and self.state.outcomes:
            result = self.backend.load_result(ws)
            if result:
                from thesean.pipeline.staleness import is_result_stale
                stale = is_result_stale(self.state.case, result)


        screen = InvestigationScreen(
            case=self.state.case,
            case_state=self.state.case_state,
            events=events,
            divergence_scores=divergence_scores,
            values_a=values_a_list,
            values_b=values_b_list,
            signals_a=signals_a,
            signals_b=signals_b,
            max_step=max_step,
            metric_ids=signal_names,
            all_metrics_data={},
            outcomes=self.state.outcomes,
            episode_idx=episode_idx,
            episode_count=episode_count,
            stale=stale,
            signal_schema=self.state.signal_schema,
            signal_translator=self.state.signal_translator,
            track_geometry=self.state.track_geometry,
        )
        self.push_screen(screen)

    _DECISION_LABELS = {
        "world_model": "World model is the primary factor",
        "planner": "Planner is the primary factor",
        "env": "Environment is the primary factor",
        "interaction": "Component interaction detected",
        "unknown": "Run isolation for attribution",
        "no_change": "No significant change",
        "not_attributable": "Not attributable with current data",
    }

    def _open_attribution(self) -> None:
        from thesean.tui.screens.attribution import AttributionWorkspaceScreen

        # Build explanations from attribution tables if available
        explanations = []
        if self.state.attributions:
            from thesean.models.explanation import Explanation

            for attr in self.state.attributions:
                label = self._DECISION_LABELS.get(attr.decision, attr.decision)
                explanations.append(Explanation(
                    id=f"expl-{attr.metric_id}",
                    event_id=self.state.events[0].id if self.state.events else "",
                    label=label,
                    confidence=max((e.confidence or 0 for e in attr.main_effects), default=0),
                    tier="tier_1" if self.state.isolation_bundle else "tier_0",
                    support_basis=[e.factor for e in attr.main_effects],
                ))

        tier = "tier_0"
        if self.state.isolation_bundle and self.state.attributions:
            tier = "tier_2"
        elif self.state.isolation_bundle:
            tier = "tier_1"

        screen = AttributionWorkspaceScreen(
            events=self.state.events,
            explanations=explanations,
            tier=tier,
            case=self.state.case,
            attributions=self.state.attributions,
        )
        self.push_screen(screen)

    # ── RunBuilderScreen messages ──

    def on_run_builder_screen_case_selected(self, event: RunBuilderScreen.CaseSelected) -> None:
        self.pop_screen()
        self.load_workspace(event.workspace)

    def on_run_builder_screen_case_edited(self, event: RunBuilderScreen.CaseEdited) -> None:
        """Handle edited case: save case.json, check staleness, update UI (WORK-01 thru WORK-04)."""
        from thesean.pipeline.case_io import save_case
        from thesean.pipeline.staleness import is_result_stale
        from thesean.tui.screens.case_verdict import CaseVerdictScreen
        from thesean.tui.screens.investigation import InvestigationScreen

        case = event.case
        workspace = event.workspace

        # Save updated case.json only -- never delete analysis/ or runs/ (WORK-04)
        save_case(case, workspace)
        self.state.case = case

        # Pop builder screen
        self.pop_screen()

        # Check staleness (WORK-02)
        result = self.backend.load_result(workspace)
        if result and self.state.outcomes:
            stale = is_result_stale(case, result)
            if isinstance(self.screen, InvestigationScreen):
                self.screen._stale = stale
                self.screen._render_focus_line()
                if stale:
                    self.notify("Case updated. Results are stale — re-evaluate or rerun analysis.")
            elif isinstance(self.screen, CaseVerdictScreen):
                if stale:
                    self.screen.set_stale(self.state.outcomes)
                    self.notify("Case updated. Results are stale — re-evaluate or rerun analysis.")
                else:
                    ws = self.state.current_workspace
                    episode_count = self.backend.get_episode_count(ws, "a") if ws else 0
                    events_by_episode = self.backend.load_events_by_episode(ws) if ws else {}
                    self.screen.set_ready(self.state.outcomes, episode_count, events_by_episode)
        else:
            self.notify("Case updated.")

    def on_run_builder_screen_case_created(self, event: RunBuilderScreen.CaseCreated) -> None:
        case = event.case
        workspace = event.workspace
        ctx = self.state.detected_context

        # Create workspace with new directory structure (D-01, D-02)
        if ctx.adapter and ctx.project_root:
            self.backend.create_workspace(workspace, case, ctx.adapter, ctx.project_root)
        else:
            # Fallback: minimal workspace without adapter binding
            from thesean.pipeline.workspace import create_workspace_dirs, write_workspace_state
            create_workspace_dirs(workspace)
            self.backend.create_case(workspace, case)
            write_workspace_state(workspace, {"case_state": "draft", "attempts": []})

        # Set app state
        self.state.case = case
        self.state.current_workspace = workspace
        self.state.case_name = workspace.name
        self.state.case_state = CaseState.DRAFT
        self.state.events = []
        self.state.outcomes = None

        # Update in-memory case list so history sees it immediately
        if workspace not in ctx.cases:
            ctx.cases.insert(0, workspace)

        # Load track geometry for braille track map
        self._load_track_geometry()

        # Navigate to case verdict
        self.pop_screen()
        self._open_case_verdict()

        # Notify user (D-19: workspace-first, eval is separate step)
        self.notify("Case loaded (not yet evaluated). Press r to run evaluation.")
