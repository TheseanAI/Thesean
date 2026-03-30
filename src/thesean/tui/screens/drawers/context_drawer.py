"""Context drawer — case config and run cards as a slide-in panel."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.events import Click
from textual.screen import ModalScreen
from textual.widgets import Static

from thesean.models.case import Case


def _short(ref: str) -> str:
    """Shorten a reference path for display."""
    if not ref:
        return "(none)"
    parts = ref.replace("\\", "/").split("/")
    return parts[-1] if parts else ref


class ContextDrawer(ModalScreen[None]):
    """Slide-in panel showing case configuration context."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    ContextDrawer {
        align: right middle;
    }
    ContextDrawer > VerticalScroll {
        width: 40%;
        height: 100%;
        background: $surface;
        border-left: solid $panel;
        padding: 1 2;
    }
    ContextDrawer .ctx-title {
        text-style: bold;
        padding-bottom: 1;
    }
    ContextDrawer .ctx-section {
        text-style: bold;
        padding: 1 0 0 0;
        color: $accent;
    }
    ContextDrawer .ctx-field {
        padding: 0 0 0 2;
        color: $text-muted;
    }
    """

    def __init__(self, case: Case | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._case = case

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static("Case Context", classes="ctx-title")
            if self._case:
                for label, run in [("Run A", self._case.run_a), ("Run B", self._case.run_b)]:
                    if run is None:
                        continue
                    yield Static(f"[{label}]", classes="ctx-section")
                    yield Static(f"World model: {_short(run.world_model_ref)}", classes="ctx-field")
                    yield Static(f"Planner: {run.planner_ref or 'cem'}", classes="ctx-field")
                    yield Static(f"Episodes: {run.num_episodes}", classes="ctx-field")

                yield Static("[Shared]", classes="ctx-section")
                yield Static(f"Track: {self._case.track_ref or '(none)'}", classes="ctx-field")
                yield Static(f"Episodes: {self._case.episode_count}", classes="ctx-field")
                seeds_str = ", ".join(str(s) for s in self._case.eval_seeds) if self._case.eval_seeds else "auto"
                yield Static(f"Seeds: {seeds_str}", classes="ctx-field")
                yield Static(f"Alignment: {self._case.alignment_method}", classes="ctx-field")
            else:
                yield Static("No case loaded.")

    def on_click(self, event: Click) -> None:
        """Dismiss when clicking outside the drawer content."""
        if self.get_widget_at(event.screen_x, event.screen_y)[0] is self:
            self.dismiss(None)

    def action_dismiss(self, result: None = None) -> None:  # type: ignore[override]
        self.dismiss(None)
