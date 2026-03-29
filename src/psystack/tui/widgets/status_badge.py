"""Status badge with color variants."""

from __future__ import annotations

from typing import Any

from textual.widgets import Static

VARIANT_CLASSES = {
    "completed": "status-completed",
    "running": "status-running",
    "failed": "status-failed",
    "skipped": "status-skipped",
    "default": "status-default",
}


class StatusBadge(Static):
    DEFAULT_CSS = """
    StatusBadge {
        padding: 0 1;
        margin: 0 1;
        min-width: 8;
        text-align: center;
    }
    StatusBadge.status-completed {
        background: $success;
        color: $text;
    }
    StatusBadge.status-running {
        background: $warning;
        color: $text;
    }
    StatusBadge.status-failed {
        background: $error;
        color: $text;
    }
    StatusBadge.status-skipped {
        color: $text-muted;
    }
    StatusBadge.status-default {
        color: $text;
    }
    """

    def __init__(self, label: str, variant: str = "default", **kwargs: Any) -> None:
        super().__init__(label, **kwargs)
        self.set_variant(variant)

    def set_variant(self, variant: str) -> None:
        for cls in VARIANT_CLASSES.values():
            self.remove_class(cls)
        css_class = VARIANT_CLASSES.get(variant, "status-default")
        self.add_class(css_class)
