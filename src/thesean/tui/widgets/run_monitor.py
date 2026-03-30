"""Run monitor — shows live pipeline stage progress."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widget import Widget
from textual.widgets import Button, Static

from thesean.tui.widgets.section_title import SectionTitle


class RunMonitor(Widget):
    DEFAULT_CSS = """
    RunMonitor {
        border: solid $panel;
        padding: 1;
        height: auto;
    }
    RunMonitor #run_title {
        text-style: bold;
    }
    RunMonitor .stage-pending {
        color: $text-muted;
    }
    RunMonitor .stage-running {
        color: $warning;
        text-style: bold;
    }
    RunMonitor .stage-completed {
        color: $success;
    }
    RunMonitor .stage-failed {
        color: $error;
    }
    """

    STAGE_NAMES = ("compare", "isolate", "attribute", "report")

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static("Pipeline not started", id="run_title")
            yield SectionTitle("Stage timeline")
            for name in self.STAGE_NAMES:
                yield Static(f"  ○ {name}  pending", id=f"stage_{name}", classes="stage-pending")
            yield Static("", id="run_detail")
            with Horizontal():
                yield Button("Cancel", id="cancel_run", variant="error")

    def start_run(self) -> None:
        self.query_one("#run_title", Static).update("Investigation in progress...")
        for name in self.STAGE_NAMES:
            w = self.query_one(f"#stage_{name}", Static)
            w.update(f"  ○ {name}  pending")
            w.remove_class("stage-running", "stage-completed", "stage-failed")
            w.add_class("stage-pending")

    def update_stage(self, stage_name: str, detail: str = "") -> None:
        self.query_one("#run_title", Static).update(f"Running: {stage_name}")
        try:
            w = self.query_one(f"#stage_{stage_name}", Static)
            w.update(f"  ● {stage_name}  running  {detail}")
            w.remove_class("stage-pending", "stage-completed", "stage-failed")
            w.add_class("stage-running")
        except Exception:
            pass

    def mark_stage_done(self, stage_name: str) -> None:
        try:
            w = self.query_one(f"#stage_{stage_name}", Static)
            w.update(f"  ● {stage_name}  completed")
            w.remove_class("stage-pending", "stage-running", "stage-failed")
            w.add_class("stage-completed")
        except Exception:
            pass

    def mark_stage_failed(self, stage_name: str, error: str = "") -> None:
        try:
            w = self.query_one(f"#stage_{stage_name}", Static)
            short_err = error[:60] if error else ""
            w.update(f"  ● {stage_name}  failed  {short_err}")
            w.remove_class("stage-pending", "stage-running", "stage-completed")
            w.add_class("stage-failed")
        except Exception:
            pass

    def mark_complete(self) -> None:
        self.query_one("#run_title", Static).update("Investigation complete!")

    def mark_failed(self, message: str) -> None:
        self.query_one("#run_title", Static).update(f"Investigation failed: {message[:80]}")
