"""Compact single-line strip showing top signal deltas."""

from __future__ import annotations

from textual.widgets import Static


class FocusSignalsStrip(Static):
    """Single-line display of top signal deltas at the current step/event."""

    DEFAULT_CSS = """
    FocusSignalsStrip {
        height: 1;
        background: $boost;
        padding: 0 1;
    }
    """

    def set_signals(self, deltas: list[tuple[str, float]]) -> None:
        """Show top signal deltas as compact line."""
        parts = [f"{name} \u0394{val:+.3f}" for name, val in deltas[:5]]
        self.update(" \u2502 ".join(parts) if parts else "")
