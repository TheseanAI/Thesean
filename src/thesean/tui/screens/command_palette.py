"""Command palette modal — fuzzy-filtered list of actions."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static

COMMANDS = [
    ("new_investigation", "New case"),
    ("open_workspace", "Open case..."),
    ("switch_case", "Switch case"),
    ("run_full", "Run full pipeline"),
    ("run_compare", "Run compare only"),
    ("rerender_report", "Re-render report"),
    ("screen_builder", "Run Builder"),
    ("screen_investigation", "Investigation"),
    ("screen_attribution", "Attribution"),
]


class CommandPaletteModal(ModalScreen[str | None]):
    DEFAULT_CSS = """
    CommandPaletteModal {
        align: center middle;
    }
    CommandPaletteModal > Vertical {
        width: 60;
        height: auto;
        max-height: 24;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    CommandPaletteModal Input {
        margin-bottom: 1;
    }
    CommandPaletteModal ListView {
        height: auto;
        max-height: 14;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Input(placeholder="Type a command...", id="cmd_input")
            yield ListView(id="cmd_list")

    def on_mount(self) -> None:
        self._populate("")

    def _populate(self, query: str) -> None:
        lv = self.query_one("#cmd_list", ListView)
        lv.clear()
        term = query.lower()
        for cmd_id, label in COMMANDS:
            if not term or term in label.lower() or term in cmd_id:
                lv.append(ListItem(Static(label), name=cmd_id))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "cmd_input":
            self._populate(event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.name:
            self.dismiss(event.item.name)

    def key_escape(self) -> None:
        self.dismiss(None)
