"""Attribution decision card — shows metric, decision, and interpretation."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from thesean.models.isolation import AttributionTable

DECISION_LABELS = {
    "weights_responsible": "World model weights are the likely cause.",
    "planner_responsible": "Planner configuration is the likely cause.",
    "both": "Both weights and planner contributed.",
    "not_attributable": "Cause could not be attributed to a single factor.",
}


class AttributionDecisionCard(Widget):
    DEFAULT_CSS = """
    AttributionDecisionCard {
        border: solid $panel;
        padding: 1;
        height: auto;
    }
    AttributionDecisionCard #attr_metric_id {
        text-style: bold;
    }
    AttributionDecisionCard #attr_decision {
        padding: 1 0;
        color: $accent;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static("No attribution loaded", id="attr_metric_id")
            yield Static("", id="attr_decision")
            yield Static("", id="attr_interpretation")

    def show_table(self, table: AttributionTable | None) -> None:
        metric_w = self.query_one("#attr_metric_id", Static)
        decision_w = self.query_one("#attr_decision", Static)
        interp_w = self.query_one("#attr_interpretation", Static)

        if table is None:
            metric_w.update("No attribution loaded")
            decision_w.update("")
            interp_w.update("")
            return

        metric_w.update(f"Metric: {table.metric_id}")
        decision_w.update(f"Decision: {table.decision}")
        interp_w.update(DECISION_LABELS.get(table.decision, table.decision))
