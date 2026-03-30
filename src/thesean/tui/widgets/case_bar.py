"""CaseBar — sticky case summary header."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.widgets import Static

from thesean.models.case import Case

if TYPE_CHECKING:
    from thesean.models.episode import OutcomeSummary


class CaseBar(Static):
    """Compact sticky header showing case metadata."""

    DEFAULT_CSS = """
    CaseBar {
        height: 2;
        background: $boost;
        padding: 0 2;
        color: $text;
        border-bottom: hkey $panel;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._case: Case | None = None
        self._case_state: str = "draft"

    def set_case(self, case: Case, case_state: str = "draft") -> None:
        self._case = case
        self._case_state = case_state
        self._refresh_content()

    def update_state(self, case_state: str) -> None:
        """Update displayed state without changing case data."""
        self._case_state = case_state
        self._refresh_content()

    def set_investigation(
        self,
        case: Case,
        episode_idx: int,
        episode_count: int,
        outcomes: OutcomeSummary | None = None,
        stale: bool = False,
    ) -> None:
        """Render investigation-specific header: case + episode + verdict + align."""
        self._case = case
        text = Text()
        text.append("Case: ", style="dim")
        text.append(case.id, style="bold")
        text.append(" \u2502 ", style="dim")
        text.append(f"Episode {episode_idx + 1}/{episode_count}", style="bold")
        text.append(" \u2502 ", style="dim")
        if outcomes:
            _verdict_styles = {
                "regression": "bold red",
                "improvement": "bold green",
                "no_change": "dim",
                "mixed": "bold yellow",
            }
            vstyle = _verdict_styles.get(outcomes.verdict, "")
            text.append(f"Verdict: {outcomes.verdict.upper()}", style=vstyle)
            if stale:
                text.append(" (stale)", style="yellow")
            if outcomes.delta_pct is not None:
                sign = "+" if outcomes.delta_pct >= 0 else ""
                text.append(f"  {outcomes.primary_metric_display} {sign}{outcomes.delta_pct:.1f}%", style="bold")
        else:
            text.append("Verdict: --", style="dim")
        text.append(" \u2502 ", style="dim")
        text.append(f"Align: {case.alignment_method}", style="")
        self.update(text)

    def _refresh_content(self) -> None:
        if not self._case:
            self.update("No case loaded")
            return

        case = self._case
        state_colors = {
            "draft": ("Draft", "dim"),
            "running": ("Running", "yellow"),
            "pending": ("Analyzing", "cyan"),
            "run_failed": ("Run failed", "red"),
            "ready": ("Ready", "green"),
        }

        text = Text()
        text.append("Case: ", style="dim")
        text.append(case.id, style="bold")
        text.append("  Track: ", style="dim")
        text.append(case.track_ref or "\u2014", style="")
        text.append("  Episodes: ", style="dim")
        text.append(str(case.episode_count), style="bold")
        text.append("  Align: ", style="dim")
        text.append(case.alignment_method, style="")
        text.append("  ", style="")

        state_label, state_style = state_colors.get(self._case_state, (self._case_state, ""))
        text.append(state_label, style=state_style)

        self.update(text)
