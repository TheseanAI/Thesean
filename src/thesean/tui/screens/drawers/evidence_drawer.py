"""Evidence drawer — raw signal traces and event windows."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.events import Click
from textual.screen import ModalScreen
from textual.widgets import Static

from thesean.models.event import Event

_SEVERITY_STYLE = {
    "critical": "cd-diff",
    "warning": "section-title",
    "info": "cd-same",
}


class EvidenceDrawer(ModalScreen[None]):
    """Slide-in panel showing raw evidence for detected events."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=True),
        Binding("q", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    EvidenceDrawer {
        align: right middle;
    }
    EvidenceDrawer > VerticalScroll {
        width: 50%;
        height: 100%;
        background: $surface;
        border-left: solid $panel;
        padding: 1 2;
    }
    EvidenceDrawer .ed-title {
        text-style: bold;
        padding-bottom: 1;
    }
    EvidenceDrawer .ed-event-header {
        text-style: bold;
        padding: 1 0 0 0;
    }
    EvidenceDrawer .ed-severity-critical {
        color: $error;
        text-style: bold;
    }
    EvidenceDrawer .ed-severity-warning {
        color: $warning;
    }
    EvidenceDrawer .ed-severity-info {
        color: $text-muted;
    }
    EvidenceDrawer .ed-detail {
        padding: 0 0 0 2;
        color: $text-muted;
    }
    EvidenceDrawer .ed-signal {
        padding: 0 0 0 4;
    }
    """

    def __init__(self, events: list[Event] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._events = events or []

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(f"Evidence ({len(self._events)} events)", classes="ed-title")
            if self._events:
                for evt in self._events:
                    sev_class = f"ed-severity-{evt.severity}"
                    yield Static(
                        f"Event: {evt.type.replace('_', ' ').title()} at step {evt.step}",
                        classes="ed-event-header",
                    )
                    yield Static(f"  Severity: {evt.severity.upper()}", classes=sev_class)
                    yield Static(f"  Score: {evt.score:.4f}", classes="ed-detail")
                    yield Static(f"  Persistence: {evt.persistence_k} steps", classes="ed-detail")
                    if evt.active_signals:
                        yield Static("  Active signals:", classes="ed-detail")
                        for sig in evt.active_signals:
                            fmt = sig.display_format or ".4f"
                            unit = f" {sig.unit}" if sig.unit else ""
                            yield Static(
                                f"    {sig.name}: {sig.value:{fmt}}{unit}",
                                classes="ed-signal",
                            )
                    if evt.local_window:
                        yield Static(
                            f"  Window: [{evt.local_window[0]}, {evt.local_window[1]}]",
                            classes="ed-detail",
                        )
                    if evt.evidence_refs:
                        yield Static("  Evidence refs:", classes="ed-detail")
                        for ref in evt.evidence_refs:
                            yield Static(f"    {ref}", classes="ed-signal")
            else:
                yield Static("No evidence available. Run the pipeline first.")

    def on_click(self, event: Click) -> None:
        """Dismiss when clicking outside the drawer content."""
        if self.get_widget_at(event.screen_x, event.screen_y)[0] is self:
            self.dismiss(None)

    def action_dismiss(self, result: None = None) -> None:  # type: ignore[override]
        self.dismiss(None)
