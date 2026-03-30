"""Event navigator — scrollable event list with severity-grouped sections."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from thesean.models.event import Event

_SEVERITY_STYLES = {
    "critical": ("\u25cf", "bold red"),
    "warning": ("\u25b2", "bold yellow"),
    "info": ("\u25cb", "dim"),
}

_TYPE_SHORT = {
    "first_signal_divergence": "sig_div",
    "first_action_divergence": "act_div",
    "first_risk_spike": "risk",
    "first_boundary_collapse": "boundary",
    "terminal": "terminal",
    "max_metric_gap": "max_gap",
    "first_divergence": "first_div",
    "divergence_window": "div_window",
    "risk_spike": "risk",
    "off_track_terminal": "off_track",
    "max_gap": "max_gap",
}


class EventNavigator(VerticalScroll):
    """Right-rail event list — grouped by investigation relevance."""

    _highlighted_idx: int = -1

    class EventClicked(Message):
        def __init__(self, event_idx: int, step: int) -> None:
            self.event_idx = event_idx
            self.step = step
            super().__init__()

    DEFAULT_CSS = """
    EventNavigator {
        width: 100%;
        height: auto;
        max-height: 50%;
        min-height: 6;
        border: round $panel;
        padding: 0;
    }
    EventNavigator .en-item {
        padding: 0 1;
        height: 1;
    }
    EventNavigator .en-item-selected {
        padding: 0 1;
        height: 1;
        background: $accent 15%;
        border-left: wide $accent;
    }
    EventNavigator .en-section {
        padding: 0 1;
        height: 1;
        color: $text-muted;
        text-style: bold;
    }
    EventNavigator .en-empty {
        padding: 1 2;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._events: list[Event] = []
        # Direct widget references — index maps to Static widget, avoids ID collisions
        self._item_widgets: list[tuple[int, Static]] = []

    def compose(self) -> ComposeResult:
        self.border_title = "Divergences"
        yield from ()

    def set_events(self, events: list[Event]) -> None:
        self._events = events
        self._highlighted_idx = -1
        self._item_widgets = []

        # Remove all existing children synchronously via remove_children
        self.remove_children()

        if not events:
            self.mount(Static("No divergences detected", classes="en-empty"))
            self.border_title = "Divergences"
            return

        suggested = [(i, e) for i, e in enumerate(events) if e.severity in ("critical", "warning")]
        other = [(i, e) for i, e in enumerate(events) if e.severity == "info"]

        to_mount: list[Static] = []

        if suggested:
            to_mount.append(Static("Suggested Path", classes="en-section"))
            for i, evt in suggested:
                w = self._build_event_widget(i, evt, selected=False)
                self._item_widgets.append((i, w))
                to_mount.append(w)

        if other:
            to_mount.append(Static("Other Divergences", classes="en-section"))
            for i, evt in other:
                w = self._build_event_widget(i, evt, selected=False)
                self._item_widgets.append((i, w))
                to_mount.append(w)

        if not suggested and not other:
            for i, evt in enumerate(events):
                w = self._build_event_widget(i, evt, selected=False)
                self._item_widgets.append((i, w))
                to_mount.append(w)

        self.mount(*to_mount)
        self.border_title = f"Divergences ({len(events)})"

    def _build_event_widget(self, idx: int, evt: Event, selected: bool) -> Static:
        line = self._build_line(idx, evt, selected)
        cls = "en-item-selected" if selected else "en-item"
        # No ID — we use _item_widgets list for direct reference
        return Static(line, classes=cls)

    def _build_line(self, idx: int, evt: Event, selected: bool) -> Text:
        icon, icon_style = _SEVERITY_STYLES.get(evt.severity, ("?", ""))
        label = _TYPE_SHORT.get(evt.type, evt.type.replace("_", " "))
        line = Text()
        line.append("> " if selected else "  ", style="bold" if selected else "")
        line.append(icon, style=icon_style)
        line.append(f" t={evt.step} ", style="bold")
        line.append(label, style="")
        return line

    def highlight(self, idx: int | None) -> None:
        """Highlight the event at idx."""
        old = self._highlighted_idx
        new = idx if idx is not None else -1
        if old == new:
            return
        self._highlighted_idx = new

        # Deselect old
        for item_idx, widget in self._item_widgets:
            if item_idx == old:
                try:
                    widget.set_classes("en-item")
                    widget.update(self._build_line(item_idx, self._events[item_idx], selected=False))
                except Exception:
                    pass
                break

        # Select new
        for item_idx, widget in self._item_widgets:
            if item_idx == new:
                try:
                    widget.set_classes("en-item-selected")
                    widget.update(self._build_line(item_idx, self._events[item_idx], selected=True))
                    widget.scroll_visible()
                except Exception:
                    pass
                break

    def on_click(self, event) -> None:
        for item_idx, widget in self._item_widgets:
            if widget is event.widget:
                self.post_message(self.EventClicked(item_idx, self._events[item_idx].step))
                return
