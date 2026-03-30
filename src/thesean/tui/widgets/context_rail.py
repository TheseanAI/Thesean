"""Context rail — left panel showing run cards and case summary."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from thesean.models.case import Case


class ContextRail(Vertical):
    """Left rail showing run configuration and case context."""

    DEFAULT_CSS = """
    ContextRail {
        width: 22;
        border: solid $panel;
        padding: 1;
    }
    ContextRail .cr-title {
        text-style: bold;
        padding-bottom: 1;
    }
    ContextRail .cr-section {
        text-style: bold;
        padding: 1 0 0 0;
        color: $accent;
    }
    ContextRail .cr-field {
        padding: 0;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Case Context", classes="cr-title")
        yield Static("No case loaded", id="cr-content")

    def set_case(self, case: Case) -> None:
        content = self.query_one("#cr-content", Static)
        lines = []

        for label, run in [("[Run A]", case.run_a), ("[Run B]", case.run_b)]:
            if run is None:
                continue
            lines.append(label)
            lines.append(f"  wm: {_short(run.world_model_ref)}")
            lines.append(f"  pln: {run.planner_ref or 'cem'}")
            lines.append(f"  ep: {run.num_episodes}")
            lines.append("")

        lines.append("[Shared]")
        lines.append(f"  track: {case.track_ref or '(none)'}")
        lines.append(f"  episodes: {case.episode_count}")
        seeds_str = ", ".join(str(s) for s in case.eval_seeds) if case.eval_seeds else "auto"
        lines.append(f"  seeds: {seeds_str}")
        lines.append(f"  align: {case.alignment_method}")

        content.update("\n".join(lines))


def _short(ref: str) -> str:
    """Shorten a reference path for display."""
    if not ref:
        return "(none)"
    # Show just filename
    parts = ref.replace("\\", "/").split("/")
    return parts[-1] if parts else ref
