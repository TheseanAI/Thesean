"""Detail pane for a selected isolation case."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from thesean.models.isolation import IsolationCase
from thesean.models.swap import SwapTestResult


class IsolationCaseDetailPane(Widget):
    DEFAULT_CSS = """
    IsolationCaseDetailPane {
        border: solid $panel;
        padding: 1;
        height: auto;
        max-height: 16;
    }
    IsolationCaseDetailPane #case_title {
        text-style: bold;
        padding-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static("Select a case to view details", id="case_title")
            yield Static("", id="case_factors")
            yield Static("", id="case_outcome")

    def show_case(
        self,
        case: IsolationCase | None,
        result: SwapTestResult | None,
    ) -> None:
        title = self.query_one("#case_title", Static)
        factors_w = self.query_one("#case_factors", Static)
        outcome_w = self.query_one("#case_outcome", Static)

        if case is None:
            title.update("Select a case to view details")
            factors_w.update("")
            outcome_w.update("")
            return

        title.update(f"Selected case: {case.test_id}")
        factors_w.update(
            f"Factors\n"
            f"  world_model: {case.factors.world_model}\n"
            f"  planner: {case.factors.planner}\n"
            f"  env: {case.factors.env}"
        )

        if result is None:
            outcome_w.update("No result available")
        elif result.error:
            outcome_w.update(f"Status: {result.status}\nError: {result.error}")
        else:
            lines = [f"Status: {result.status}"]
            for mr in result.metrics[:5]:
                lines.append(f"  {mr.metric_id}: {mr.value:.4f}")
            if len(result.metrics) > 5:
                lines.append(f"  ... and {len(result.metrics) - 5} more")
            outcome_w.update("\n".join(lines))
