"""Section title widget."""

from __future__ import annotations

from textual.widgets import Static


class SectionTitle(Static):
    DEFAULT_CSS = """
    SectionTitle {
        padding: 1 0 0 0;
        text-style: bold;
        color: $accent;
    }
    """
