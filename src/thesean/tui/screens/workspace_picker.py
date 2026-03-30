"""Workspace picker modal — enter path or select from recents."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, ListView, Static


class WorkspacePickerModal(ModalScreen[Path | None]):
    DEFAULT_CSS = """
    WorkspacePickerModal {
        align: center middle;
    }
    WorkspacePickerModal > Vertical {
        width: 70;
        height: auto;
        max-height: 30;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    WorkspacePickerModal #picker_title {
        text-style: bold;
        padding-bottom: 1;
    }
    WorkspacePickerModal Input {
        margin: 0 0 1 0;
    }
    WorkspacePickerModal ListView {
        height: auto;
        max-height: 10;
        margin-bottom: 1;
    }
    WorkspacePickerModal Horizontal {
        height: auto;
        align-horizontal: right;
    }
    WorkspacePickerModal Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Open Workspace", id="picker_title")
            yield Input(placeholder="Enter workspace path...", id="path_input")
            yield Static("Recent workspaces:", classes="text-muted")
            yield ListView(id="recent_workspaces")
            with Horizontal():
                yield Button("Cancel", id="cancel", variant="default")
                yield Button("Open", id="open", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open":
            inp = self.query_one("#path_input", Input)
            if inp.value.strip():
                self.dismiss(Path(inp.value.strip()))
            else:
                self.dismiss(None)
        elif event.button.id == "cancel":
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.name:
            self.dismiss(Path(event.item.name))
