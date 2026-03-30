"""Artifact list — clickable file list."""

from __future__ import annotations

from pathlib import Path

from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from thesean.reporting.types import ArtifactRef


class ArtifactList(ListView):
    DEFAULT_CSS = """
    ArtifactList {
        height: 1fr;
    }
    """

    class ArtifactClicked(Message):
        def __init__(self, path: str) -> None:
            self.path = path
            super().__init__()

    def load_artifacts(self, artifacts: list[ArtifactRef]) -> None:
        self.clear()
        for art in artifacts:
            label = Path(art.path).name
            self.append(ListItem(Static(f"[{art.kind}] {art.label} — {label}"), name=art.path))

    def load_paths(self, paths: list[Path]) -> None:
        self.clear()
        for p in paths:
            self.append(ListItem(Static(p.name), name=str(p)))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.name:
            self.post_message(self.ArtifactClicked(event.item.name))
