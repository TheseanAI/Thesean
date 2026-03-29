"""VerdictStrip — full-width verdict surface between CaseBar and inv-main."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Static

if TYPE_CHECKING:
    from psystack.models.episode import OutcomeSummary


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


class VerdictStrip(Static):
    """Full-width 3-line verdict strip. Height=3, placed between CaseBar and #inv-main."""

    DEFAULT_CSS = """
    VerdictStrip {
        height: 3;
        padding: 0 1;
        background: $surface;
        color: $text;
        border-bottom: hkey $panel;
    }
    """

    def set_awaiting(self) -> None:
        self.set_classes("vs-awaiting")
        self.update("Ready to evaluate — press  r  to run.\n\n")

    def set_running(self) -> None:
        self.set_classes("vs-running")
        self._side_progress: dict[str, tuple[int, int]] = {}
        self.update("Evaluation in progress...\n\n")

    def set_progress(self, side: str, episode: int, total: int,
                     elapsed: float = 0.0, global_ep: int = 0, total_episodes: int = 0) -> None:
        self.set_classes("vs-running")
        # Track per-side progress for interleaved parallel updates
        if not hasattr(self, "_side_progress"):
            self._side_progress = {}  # type: ignore[no-redef]
        self._side_progress[side] = (episode, total)

        # Build combined display
        parts = []
        for s in ("a", "b"):
            if s in self._side_progress:
                ep, tot = self._side_progress[s]
                parts.append(f"Side {s.upper()}: {ep}/{tot}")
        progress_line = "  |  ".join(parts)

        elapsed_str = _fmt_duration(elapsed)
        eta_str = ""
        if global_ep > 1 and total_episodes > 0:
            per_ep = elapsed / (global_ep - 1)
            remaining = per_ep * (total_episodes - global_ep + 1)
            eta_str = f"  ~{_fmt_duration(remaining)} remaining"
        self.update(f"Running evaluation — {progress_line}\n[dim]{elapsed_str} elapsed{eta_str}[/dim]\n")

    def set_pending(self) -> None:
        self.set_classes("vs-pending")
        self.update("Computing outcomes...\n\n")

    def set_verdict(self, outcomes: OutcomeSummary) -> None:
        verdict = outcomes.verdict
        headline = outcomes.verdict_headline
        metric_line = outcomes.primary_metric_line
        findings_line = outcomes.findings_count_line

        # Apply color markup to headline based on verdict (UI-SPEC §2.4)
        if verdict == "regression":
            cls = "vs-verdict-regression"
            colored_headline = f"[red]{headline}[/red]"
        elif verdict == "improvement":
            cls = "vs-verdict-improvement"
            colored_headline = f"[green]{headline}[/green]"
        elif verdict == "no_change":
            cls = "vs-verdict-nochange"
            colored_headline = f"[dim]{headline}[/dim]"
        else:  # mixed
            cls = "vs-verdict-mixed"
            colored_headline = f"[yellow]{headline}[/yellow]"

        self.set_classes(cls)
        self.update(f"{colored_headline}\n[dim]{metric_line}[/dim]\n[dim]{findings_line}[/dim]")

    def set_stale(self, outcomes: OutcomeSummary) -> None:
        """Show verdict with stale overlay (WORK-03)."""
        verdict_text = outcomes.verdict_headline
        self.set_classes("vs-stale")
        self.update(
            f"[yellow bold]Results may be outdated[/yellow bold] — case was edited since last evaluation.\n"
            f"[dim]{verdict_text}[/dim]\n"
            f"[dim]Press  r  to re-evaluate  |  A  for analysis-only rerun[/dim]"
        )

    def set_analysis_failed(self) -> None:
        self.set_classes("vs-analysis-failed")
        self.update("[yellow]Analysis failed — run data saved. Press  r  to retry.[/yellow]\n\n")
