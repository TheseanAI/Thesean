"""Metric comparison table — clickable rows, sortable columns, filterable."""

from __future__ import annotations

from typing import Any

from textual.message import Message
from textual.widgets import DataTable

from psystack.models.comparison import MetricComparison


class MetricTable(DataTable):
    DEFAULT_CSS = """
    MetricTable {
        height: 1fr;
        width: 1fr;
    }
    """

    class MetricSelected(Message):
        def __init__(self, metric_id: str) -> None:
            self.metric_id = metric_id
            super().__init__()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._all_metrics: list[MetricComparison] = []
        self._displayed_metrics: list[MetricComparison] = []

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Metric", "Status", "Baseline", "Candidate", "Delta badness", "Adj. p")

    def load_metrics(self, metrics: list[MetricComparison]) -> None:
        self._all_metrics = list(metrics)
        self._displayed_metrics = list(metrics)
        self._render_rows()

    def apply_filters(
        self,
        regressions_only: bool = False,
        significant_only: bool = False,
        search: str = "",
    ) -> None:
        filtered = self._all_metrics
        if regressions_only:
            filtered = [m for m in filtered if m.status == "regression"]
        if significant_only:
            filtered = [m for m in filtered if m.significant]
        if search:
            term = search.lower()
            filtered = [m for m in filtered if term in m.metric_id.lower()]
        self._displayed_metrics = filtered
        self._render_rows()

    def _render_rows(self) -> None:
        self.clear()
        for m in self._displayed_metrics:
            p_str = f"{m.p_value_adj:.4f}" if m.p_value_adj is not None else "—"
            self.add_row(
                m.metric_id,
                m.status,
                f"{m.baseline_value:.4f}",
                f"{m.candidate_value:.4f}",
                f"{m.delta_badness:+.4f}",
                p_str,
                key=m.metric_id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            self.post_message(self.MetricSelected(event.row_key.value))
