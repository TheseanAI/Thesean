"""ActionBar — reusable bottom button bar for screen actions."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button

# (label, id, variant)
ButtonDef = tuple[str, str, str]


class ActionBar(Horizontal):
    """Compact horizontal bar of action buttons. Screens own all gating logic."""

    DEFAULT_CSS = """
    ActionBar {
        dock: bottom;
        height: auto;
        padding: 0 1;
        background: $boost;
        border-top: hkey $panel;
    }
    ActionBar Button {
        min-width: 8;
        height: 1;
        margin: 0 0 0 1;
    }
    ActionBar Button:disabled {
        opacity: 0.4;
    }
    """

    def __init__(self, buttons: list[ButtonDef], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._buttons = buttons

    def compose(self) -> ComposeResult:
        for label, btn_id, variant in self._buttons:
            btn = Button(label, id=btn_id, variant=variant)  # type: ignore[arg-type]
            btn.can_focus = False
            yield btn
