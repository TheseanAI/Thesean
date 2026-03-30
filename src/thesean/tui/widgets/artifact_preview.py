"""Artifact preview pane — shows text/JSON content."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static


class ArtifactPreviewPane(Widget):
    DEFAULT_CSS = """
    ArtifactPreviewPane {
        border: solid $panel;
        padding: 1;
        width: 1fr;
        height: 1fr;
    }
    ArtifactPreviewPane #preview_file_title {
        text-style: bold;
        padding-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static("Select a file to preview", id="preview_file_title")
            yield Static("", id="preview_file_content")

    def show_text(self, title: str, content: str) -> None:
        self.query_one("#preview_file_title", Static).update(title)
        if len(content) > 10_000:
            content = content[:10_000] + "\n\n... (truncated)"
        self.query_one("#preview_file_content", Static).update(content)
