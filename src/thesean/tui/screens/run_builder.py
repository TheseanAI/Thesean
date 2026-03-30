"""Run Builder Screen — configure and launch a comparison case."""

from __future__ import annotations

import contextlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Rule, Select, Static

from thesean.models.case import Case
from thesean.models.run import Run
from thesean.tui.widgets.run_config_panel import RunConfigPanel


class PlannerConfigModal(ModalScreen[dict[str, Any]]):
    """Overlay for planner settings to avoid layout warping."""

    DEFAULT_CSS = """
    PlannerConfigModal {
        align: center middle;
    }
    #planner-modal-card {
        width: auto;
        max-width: 50;
        height: auto;
        padding: 1 2;
        background: $boost;
        border: none;
        outline: none;
    }
    #planner-modal-grid {
        layout: grid;
        grid-size: 2;
        grid-gutter: 1 2;
        height: auto;
        margin-bottom: 1;
    }
    #planner-modal-grid Vertical {
        height: auto;
    }
    #planner-modal-card .rcp-label {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }
    #planner-modal-card .rcp-field-label {
        color: $text-muted;
        margin: 0;
        padding: 0 1;
    }
    #planner-modal-card Input {
        width: 100%;
        max-width: 16;
        margin: 0;
    }
    #planner-modal-actions {
        height: auto;
        margin-top: 1;
        align: center middle;
        border-top: tall $background;
        padding-top: 1;
    }
    #planner-modal-actions Button {
        margin: 0 1;
    }
    """

    def __init__(self, config: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="planner-modal-card"):
            yield Static("Planner Settings", classes="rcp-label")

            with Vertical(id="planner-modal-grid"):
                with Vertical():
                    yield Static("Horizon", classes="rcp-field-label")
                    yield Input(value=str(self.config["horizon"]), id="horizon", type="integer")

                with Vertical():
                    yield Static("Num Candidates", classes="rcp-field-label")
                    yield Input(value=str(self.config["num_candidates"]), id="num_candidates", type="integer")

                with Vertical():
                    yield Static("Iterations", classes="rcp-field-label")
                    yield Input(value=str(self.config["iterations"]), id="iterations", type="integer")

                with Vertical():
                    yield Static("Num Elites", classes="rcp-field-label")
                    yield Input(value=str(self.config["num_elites"]), id="num_elites", type="integer")

                with Vertical():
                    yield Static("Seed", classes="rcp-field-label")
                    yield Input(value=str(self.config["seed"]), id="seed", type="integer")

            with Horizontal(id="planner-modal-actions"):
                yield Button("Save", id="save", variant="success")
                yield Button("Cancel", id="cancel")
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            new_config = {
                "horizon": int(self.query_one("#horizon", Input).value),
                "num_candidates": int(self.query_one("#num_candidates", Input).value),
                "iterations": int(self.query_one("#iterations", Input).value),
                "num_elites": int(self.query_one("#num_elites", Input).value),
                "seed": int(self.query_one("#seed", Input).value),
            }
            self.dismiss(new_config)
        else:
            self.dismiss(None)


class RunBuilderScreen(Screen):
    """Full-screen run builder — always-compare layout with shared case config."""

    class CaseCreated(Message):
        def __init__(self, case: Case, workspace: Path) -> None:
            self.case = case
            self.workspace = workspace
            super().__init__()

    class CaseEdited(Message):
        def __init__(self, case: Case, workspace: Path) -> None:
            self.case = case
            self.workspace = workspace
            super().__init__()

    BINDINGS = [
        Binding("escape", "cancel", "Back"),
    ]

    DEFAULT_CSS = """
    RunBuilderScreen {
        layout: vertical;
        background: $background;
        align: center middle;
    }

    #rb-main-card {
        width: 76;
        height: auto;
        background: transparent;
        border: round $panel;
        padding: 1 2;
        outline: none;
        overflow: hidden hidden;
    }

    /* ── Logo row ── */
    RunBuilderScreen #rb-logo-row {
        width: 100%;
        height: auto;
        align: center middle;
        margin-bottom: 1;
    }
    RunBuilderScreen #rb-nn-left,
    RunBuilderScreen #rb-nn-right {
        width: auto;
        height: auto;
        color: $primary;
        padding: 0 1;
    }
    RunBuilderScreen #rb-logo {
        width: auto;
        height: auto;
        color: $primary;
        padding: 0 1;
    }

    /* ── Shared config fields ── */
    RunBuilderScreen #rb-shared-config {
        height: auto;
        padding: 0;
        border: none;
        background: transparent;
        margin-bottom: 0;
    }
    RunBuilderScreen #rb-shared-config .rcp-field-label {
        color: $text-muted;
        margin: 0;
        padding: 0 1;
    }
    RunBuilderScreen #rb-shared-config Select,
    RunBuilderScreen #rb-shared-config Input {
        width: 100%;
        margin: 0;
    }

    /* Track + Episodes + Overrides (GRID) */
    RunBuilderScreen #rb-shared-row {
        layout: grid;
        grid-size: 2;
        grid-gutter: 1 2;
        height: auto;
        width: 100%;
    }

    /* Field group inside grid cells */
    RunBuilderScreen .rb-field-group {
        height: auto;
    }

    /* ── Divider ── */
    RunBuilderScreen Rule {
        margin: 1 0;
        color: $panel;
    }

    /* ── Run panels side by side (GRID) ── */
    RunBuilderScreen #rb-panels {
        layout: grid;
        grid-size: 2;
        grid-gutter: 0 2;
        height: auto;
        width: 100%;
        margin-bottom: 0;
    }

    /* ── Actions footer ── */
    RunBuilderScreen #rb-actions {
        width: 100%;
        height: auto;
        min-height: 3;
        padding: 0;
        align-horizontal: center;
        margin-top: 2;
    }
    RunBuilderScreen #rb-actions Button {
        margin: 0 1;
    }
    RunBuilderScreen Button#rb-build {
        background: $success;
        color: $background;
    }
    RunBuilderScreen Button#rb-build:hover {
        background: $success-darken-1;
        color: $background;
    }
    RunBuilderScreen #rb-history {
        background: $panel;
        color: $text;
    }
    RunBuilderScreen #rb-history:hover {
        background: $primary;
        color: $background;
    }

    /* ── Quit hint ── */
    RunBuilderScreen #rb-quit-hint {
        width: 76;
        height: auto;
        text-align: left;
        color: $text-muted;
        padding: 0 0 0 1;
        margin-top: 0;
    }
    """

    class CaseSelected(Message):
        def __init__(self, workspace: Path) -> None:
            self.workspace = workspace
            super().__init__()

    def __init__(
        self,
        weights: list[dict[str, Any]] | None = None,
        envs: list[str] | None = None,
        project_root: Path | None = None,
        adapter_name: str | None = None,
        cases: list[Path] | None = None,
        edit_case: Case | None = None,
        edit_workspace: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._weights = weights or []
        self._envs = envs or []
        self._project_root = project_root
        self._adapter_name = adapter_name
        self._cases = cases or []
        self._edit_case = edit_case
        self._edit_workspace = edit_workspace

    def compose(self) -> ComposeResult:
        with Vertical(id="rb-main-card"):
            with Horizontal(id="rb-logo-row"):
                yield Static(
                    "o⠤⠤⠬⠤⠤⡀\n"
                    "⠀⠀o⠤⠬⠤o\n"
                    "o⠤⠤⠼⠤⠤⠃",
                    id="rb-nn-left",
                )
                yield Static(
                    "▀▀█▀▀ █  █ █▀▀ █▀▀▀ █▀▀ █▀▀█ █▀▀▄\n"
                    "  █   █▀▀█ █▀▀  ▀▀█ █▀▀ █▄▄█ █  █\n"
                    "  ▀   ▀  ▀ ▀▀▀ ▀▀▀  ▀▀▀ ▀  ▀ ▀  ▀",
                    id="rb-logo",
                )
                yield Static(
                    "⠀⠀o⠑⠢⡀\n"
                    "o⠤⠬⠤o⠤⠤o\n"
                    "⠀⠀o⡠⠔⠁",
                    id="rb-nn-right",
                )

            # Shared case-level config
            with Vertical(id="rb-shared-config"):
                with Vertical(id="rb-shared-row"):
                    with Vertical(classes="rb-field-group"):
                        yield Static("Track", classes="rcp-field-label")
                        yield Select(
                            [(e, e) for e in self._envs],
                            id="rb-track",
                            allow_blank=True,
                            prompt="Select track...",
                        )
                    with Vertical(classes="rb-field-group"):
                        yield Static("Episodes", classes="rcp-field-label")
                        yield Input(value="5", id="rb-episodes", type="integer")
                    with Vertical(classes="rb-field-group"):
                        yield Static("Max Steps", classes="rcp-field-label")
                        yield Input(value="", id="rb-env-max-steps", placeholder="default (1000)")
                    with Vertical(classes="rb-field-group"):
                        yield Static("Max Speed", classes="rcp-field-label")
                        yield Input(value="", id="rb-env-max-speed", placeholder="default (50.0)")

            yield Rule(line_style="heavy")

            # Run panels side by side
            with Vertical(id="rb-panels"):
                yield RunConfigPanel(
                    "Run A (baseline)",
                    "run_a",
                    weights=self._weights,
                    envs=self._envs,
                )
                yield RunConfigPanel(
                    "Run B (candidate)",
                    "run_b",
                    weights=self._weights,
                    envs=self._envs,
                    id="rb-panel-b",
                )

            # Actions
            with Horizontal(id="rb-actions"):
                yield Button("History", id="rb-history")
                yield Button("Build Case", id="rb-build", variant="success")
        yield Static("Quit (Ctrl+C)", id="rb-quit-hint")

    def _populate_from_case(self, case: Case) -> None:
        """Pre-populate widgets from an existing case for edit mode."""
        track_select = self.query_one("#rb-track", Select)
        if case.track_ref and not case.track_ref.startswith("Select."):
            track_select.value = case.track_ref
        else:
            track_select.clear()
        episodes_input = self.query_one("#rb-episodes", Input)
        episodes_input.value = str(case.episode_count)

        # Restore env overrides (now flat in UI)
        if case.shared_env_overrides:
            overrides = case.shared_env_overrides
            if "max_steps" in overrides:
                self.query_one("#rb-env-max-steps", Input).value = str(overrides["max_steps"])
            if "max_speed" in overrides:
                self.query_one("#rb-env-max-speed", Input).value = str(overrides["max_speed"])

        panels = list(self.query(RunConfigPanel))
        if panels:
            panels[0].set_weight(case.run_a.world_model_ref)
            # Restore planner config and seed for run A
            if case.run_a.planner_config:
                panels[0].set_planner_config(case.run_a.planner_config)
            panels[0].set_seed(case.run_a.seed)
        if len(panels) >= 2 and case.run_b:
            panels[1].set_weight(case.run_b.world_model_ref)
            if case.run_b.planner_config:
                panels[1].set_planner_config(case.run_b.planner_config)
            panels[1].set_seed(case.run_b.seed)

    def on_mount(self) -> None:
        if self._edit_case:
            self._populate_from_case(self._edit_case)

    def _collect_env_overrides(self) -> dict[str, Any]:
        """Collect non-empty env override values from inputs."""
        overrides: dict[str, Any] = {}
        max_steps_val = self.query_one("#rb-env-max-steps", Input).value.strip()
        if max_steps_val:
            with contextlib.suppress(ValueError):
                overrides["max_steps"] = int(max_steps_val)
        max_speed_val = self.query_one("#rb-env-max-speed", Input).value.strip()
        if max_speed_val:
            with contextlib.suppress(ValueError):
                overrides["max_speed"] = float(max_speed_val)
        return overrides

    def _build_run(self, run_id: str, panel: RunConfigPanel) -> Run:
        return Run(
            id=run_id,
            world_model_ref=panel.selected_weight or "",
            planner_ref=panel.selected_planner,
            planner_config=panel.planner_config_dict,
            seed=panel.selected_seed,
        )

    def _build_case(self) -> Case | None:
        panels = list(self.query(RunConfigPanel))
        if not panels:
            return None

        a = panels[0]
        date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        short_id = uuid.uuid4().hex[:6]
        case_name = f"case-{date_str}-{short_id}"

        # Shared config
        track_select = self.query_one("#rb-track", Select)
        raw_val = track_select.value
        track_ref = str(raw_val) if raw_val not in (None, Select.BLANK, Select.NULL) else ""
        episodes_input = self.query_one("#rb-episodes", Input)
        episode_count = int(episodes_input.value) if episodes_input.value else 5
        env_overrides = self._collect_env_overrides()

        # Build runs
        run_a = self._build_run("run-a", a)
        run_b = self._build_run("run-b", panels[1]) if len(panels) >= 2 else None

        return Case(
            id=case_name,
            track_ref=track_ref,
            episode_count=episode_count,
            eval_seeds=None,
            shared_env_overrides=env_overrides,
            run_a=run_a,
            run_b=run_b,
        )

    def _workspace_for_case(self, case: Case) -> Path:
        root = self._project_root or Path.cwd()
        return root / ".thesean" / "cases" / case.id

    def _on_history_picked(self, path: Path | None) -> None:
        if path is not None:
            self.post_message(self.CaseSelected(workspace=path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "planner_btn":
            # Identify which panel the button belongs to
            panel = event.button.parent
            if isinstance(panel, RunConfigPanel):
                self.app.push_screen(
                    PlannerConfigModal(panel.planner_config),
                    callback=lambda config: self._on_planner_modal_dismissed(panel, config),
                )
        elif event.button.id == "rb-history":
            from thesean.tui.screens.case_history import CaseHistoryModal

            self.app.push_screen(
                CaseHistoryModal(cases=self._cases),
                callback=self._on_history_picked,
            )
        elif event.button.id == "rb-build":
            case = self._build_case()
            if case is None:
                self.notify("Could not build case", severity="error")
                return
            if self._edit_case and self._edit_workspace:
                # Edit mode: preserve original case ID, post CaseEdited
                case.id = self._edit_case.id
                self.post_message(self.CaseEdited(case, self._edit_workspace))
            else:
                workspace = self._workspace_for_case(case)
                self.post_message(self.CaseCreated(case, workspace))

    def _on_planner_modal_dismissed(self, panel: RunConfigPanel, config: dict[str, Any] | None) -> None:
        if config is not None:
            panel.set_planner_config(config)
            self.notify(f"Updated planner for {panel._label}")

    def action_cancel(self) -> None:
        self.app.pop_screen()
