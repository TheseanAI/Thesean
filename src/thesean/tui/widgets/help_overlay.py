"""HelpOverlay — toggleable command list popup."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

# (key, description) pairs — grouped
_COMMANDS: list[tuple[str, str]] = [
    ("r", "Run evaluation"),
    ("A", "Reanalyze"),
    ("E", "Edit case"),
    ("x", "Export report"),
    ("e", "Evidence drawer"),
    ("c", "Context drawer"),
    ("a", "Attribution"),
    ("b", "Builder"),
    ("", ""),
    ("j / ]", "Next event"),
    ("k / [", "Prev event"),
    (", / . / l", "Step back / forward"),
    ("H / L", "Step back / forward 10"),
    ("", ""),
    ("n / N", "Next / prev episode"),
    ("m", "Cycle signal"),
    ("t", "Cycle timeline mode"),
    ("w", "Cycle event window"),
    ("v", "Cycle live view"),
    ("", ""),
    ("esc", "Back"),
    ("h", "Close help"),
]


class HelpOverlay(Vertical):
    """Floating command reference panel."""

    DEFAULT_CSS = """
    HelpOverlay {
        display: none;
        dock: bottom;
        height: auto;
        max-height: 70%;
        background: $surface;
        border-top: tall $accent;
        padding: 1 2;
    }
    HelpOverlay.visible {
        display: block;
    }
    HelpOverlay .help-title {
        text-style: bold;
        color: $accent;
        padding: 0 0 1 0;
    }
    HelpOverlay .help-row {
        height: 1;
        padding: 0 1;
    }
    HelpOverlay .help-key {
        width: 12;
        text-style: bold;
        color: $text;
    }
    HelpOverlay .help-sep {
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Commands", classes="help-title")
        for key, desc in _COMMANDS:
            if not key and not desc:
                yield Static("", classes="help-sep")
            else:
                yield Static(f"  {key:<10} {desc}", classes="help-row")

    def toggle(self) -> None:
        self.toggle_class("visible")

    @property
    def is_visible(self) -> bool:
        return self.has_class("visible")
