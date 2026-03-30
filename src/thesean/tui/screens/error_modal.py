"""Error modal — shows human-readable error with dismiss button."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ErrorModal(ModalScreen[None]):
    DEFAULT_CSS = """
    ErrorModal {
        align: center middle;
    }
    ErrorModal > Vertical {
        width: 60;
        height: auto;
        max-height: 20;
        border: thick $error 80%;
        background: $surface;
        padding: 1 2;
    }
    ErrorModal #error_title {
        text-style: bold;
        color: $error;
        padding-bottom: 1;
    }
    ErrorModal #error_message {
        padding: 1;
        border: solid $panel;
        margin-bottom: 1;
    }
    ErrorModal Horizontal {
        height: auto;
        align-horizontal: right;
    }
    """

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._title, id="error_title")
            yield Static(self._message, id="error_message")
            with Horizontal():
                yield Button("Close", id="close", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss(None)
