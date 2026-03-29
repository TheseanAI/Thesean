"""Isolation case table — shows swap test cases with factor configurations."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import DataTable

from psystack.models.isolation import IsolationResultBundle


class IsolationCaseTable(DataTable):
    DEFAULT_CSS = """
    IsolationCaseTable {
        height: 1fr;
        width: 1fr;
    }
    """

    class CaseSelected(Message):
        def __init__(self, case_id: str) -> None:
            self.case_id = case_id
            super().__init__()

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Case", "WM", "Planner", "Env", "Result summary")

    def load_bundle(self, bundle: IsolationResultBundle | None) -> None:
        self.clear()
        if bundle is None:
            return

        result_map = {r.test_id: r for r in bundle.swap_results}
        for case in bundle.cases:
            result = result_map.get(case.test_id)
            summary: str = result.status if result else "—"
            if result and result.error:
                summary = f"failed: {result.error[:30]}"
            self.add_row(
                case.test_id,
                case.factors.world_model,
                case.factors.planner,
                case.factors.env,
                summary,
                key=case.test_id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            self.post_message(self.CaseSelected(event.row_key.value))
