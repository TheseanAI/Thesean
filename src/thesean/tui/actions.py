"""Centralized action dispatch for the TUI."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from thesean.tui.app import TheSeanApp
    from thesean.tui.services import TuiBackendService


class TheSeanActions:
    def __init__(self, app: TheSeanApp, backend: TuiBackendService) -> None:
        self.app = app
        self.backend = backend

    def open_workspace_picker(self) -> None:
        from thesean.tui.screens.workspace_picker import WorkspacePickerModal
        self.app.push_screen(WorkspacePickerModal(), callback=self._on_workspace_picked)

    def _on_workspace_picked(self, path: Path | None) -> None:
        if path is not None:
            self.app.load_workspace(path)

    def new_investigation(self) -> None:
        """Open the Run Builder screen for new case creation."""
        self.app._open_run_builder()

    def switch_case(self) -> None:
        """Show case picker for current project + recent external cases."""
        from thesean.tui.detection import load_recent_cases

        ctx = self.app.state.detected_context
        cases = list(ctx.cases)

        # Also add recent cases from other projects
        recents = load_recent_cases()
        for r in recents:
            if r.project:
                p = Path(r.project) / ".thesean" / "cases" / r.case
                if p.is_dir() and p not in cases:
                    cases.append(p)

        if not cases:
            self.app.notify("No cases found.")
            return

        from thesean.tui.screens.workspace_picker import WorkspacePickerModal
        self.app.push_screen(WorkspacePickerModal(), callback=self._on_workspace_picked)

    def run_investigation(self) -> None:
        if self.app.state.current_workspace is None:
            self.app.show_error("No workspace", "Open a workspace before running.")
            return
        self.app.run_pipeline_action()

    def run_compare(self) -> None:
        if self.app.state.current_workspace is None:
            self.app.show_error("No workspace", "Open a workspace before running compare.")
            return
        self.app.run_pipeline_action(compare_only=True)

    def run_diagnosis(self) -> None:
        """Run isolate stage only."""
        if self.app.state.current_workspace is None:
            self.app.show_error("No workspace", "Open a workspace before running diagnosis.")
            return
        self.app.run_pipeline_action(isolate_only=True)

    def rerender_report(self) -> None:
        if self.app.state.current_workspace is None:
            return
        self.app.run_pipeline_action(report_only=True)

    def open_artifact(self, path: str) -> None:
        webbrowser.open(path)
