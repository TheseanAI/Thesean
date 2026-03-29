"""Detail pane for a selected metric comparison."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static

from psystack.models.comparison import MetricComparison


class MetricDetailPane(Widget):
    DEFAULT_CSS = """
    MetricDetailPane {
        border: solid $panel;
        padding: 1;
        height: auto;
        max-height: 18;
    }
    MetricDetailPane #metric_title {
        text-style: bold;
        padding-bottom: 1;
    }
    """

    class OpenIsolation(Message):
        def __init__(self, metric_id: str) -> None:
            self.metric_id = metric_id
            super().__init__()

    class OpenAttribution(Message):
        def __init__(self, metric_id: str) -> None:
            self.metric_id = metric_id
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_metric_id: str | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static("Select a metric to view details", id="metric_title")
            yield Static("", id="metric_summary")
            yield Static("", id="baseline_episode_values")
            yield Static("", id="candidate_episode_values")
            with Horizontal():
                yield Button("Open diagnosis", id="open_isolation", variant="default")
                yield Button("View raw artifact", id="view_raw_compare", variant="default")

    def show_metric(self, metric: MetricComparison | None) -> None:
        title = self.query_one("#metric_title", Static)
        summary = self.query_one("#metric_summary", Static)
        baseline_ep = self.query_one("#baseline_episode_values", Static)
        candidate_ep = self.query_one("#candidate_episode_values", Static)

        if metric is None:
            self._current_metric_id = None
            title.update("Select a metric to view details")
            summary.update("")
            baseline_ep.update("")
            candidate_ep.update("")
            return

        self._current_metric_id = metric.metric_id
        title.update(f"Selected: {metric.metric_id}")

        ci_str = f"[{metric.ci_low:.4f}, {metric.ci_high:.4f}]" if metric.ci_low is not None else "—"
        p_str = f"{metric.p_value_adj:.4f}" if metric.p_value_adj is not None else "—"
        sig_str = "yes" if metric.significant else "no"
        summary.update(
            f"Delta: {metric.delta:+.4f}  Delta badness: {metric.delta_badness:+.4f}\n"
            f"CI: {ci_str}  p_adj: {p_str}  significant: {sig_str}\n"
            f"Status: {metric.status}  Higher is better: {metric.higher_is_better}"
        )

        bl_vals = ", ".join(f"{v:.3f}" for v in metric.baseline_per_episode[:10])
        if len(metric.baseline_per_episode) > 10:
            bl_vals += ", ..."
        baseline_ep.update(f"Baseline per-episode: [{bl_vals}]")

        cd_vals = ", ".join(f"{v:.3f}" for v in metric.candidate_per_episode[:10])
        if len(metric.candidate_per_episode) > 10:
            cd_vals += ", ..."
        candidate_ep.update(f"Candidate per-episode: [{cd_vals}]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._current_metric_id is None:
            return
        if event.button.id == "open_isolation":
            self.post_message(self.OpenIsolation(self._current_metric_id))
