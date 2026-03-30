"""Effect estimate table for attribution view."""

from __future__ import annotations

from textual.widgets import DataTable

from thesean.models.isolation import EffectEstimate


class EffectTable(DataTable):
    DEFAULT_CSS = """
    EffectTable {
        height: auto;
        max-height: 10;
    }
    """

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("Factor", "Effect", "Confidence", "Support tests")

    def load_effects(self, effects: list[EffectEstimate]) -> None:
        self.clear()
        for e in effects:
            conf_str = f"{e.confidence:.2f}" if e.confidence is not None else "—"
            support_str = ", ".join(e.support_tests) if e.support_tests else "—"
            self.add_row(
                e.factor,
                f"{e.effect:+.4f}",
                conf_str,
                support_str,
            )
