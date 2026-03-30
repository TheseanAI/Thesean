"""Explanation card — confidence bar, tier badge, and support basis."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from thesean.models.explanation import Explanation

_TIER_LABELS = {
    "tier_0": "Tier 0: Correlational",
    "tier_1": "Tier 1: Component-isolated",
    "tier_2": "Tier 2: Counterfactual",
    "tier_3": "Tier 3: Mechanistic",
}


def _confidence_bar(confidence: float, width: int = 20) -> str:
    """Render a text-mode confidence bar."""
    filled = int(confidence * width)
    return "#" * filled + "-" * (width - filled)


class ExplanationCard(Vertical):
    """Displays an explanation with confidence visualization."""

    DEFAULT_CSS = """
    ExplanationCard {
        height: auto;
        border: solid $panel;
        padding: 1;
        margin: 0 0 1 0;
    }
    ExplanationCard .ec-label {
        text-style: bold;
    }
    ExplanationCard .ec-tier {
        color: $accent;
    }
    ExplanationCard .ec-confidence {
        padding: 0;
    }
    ExplanationCard .ec-details {
        color: $text-muted;
    }
    """

    def __init__(self, explanation: Explanation, rank: int = 1, **kwargs) -> None:
        super().__init__(**kwargs)
        self._explanation = explanation
        self._rank = rank

    def compose(self) -> ComposeResult:
        ex = self._explanation
        yield Static(f"{self._rank}. {ex.label}", classes="ec-label")
        yield Static(_TIER_LABELS.get(ex.tier, ex.tier), classes="ec-tier")
        yield Static(
            f"  confidence: {ex.confidence:.2f} [{_confidence_bar(ex.confidence)}]",
            classes="ec-confidence",
        )
        if ex.support_basis:
            yield Static(f"  basis: {' | '.join(ex.support_basis)}", classes="ec-details")
        if ex.competing:
            yield Static(f"  competing: {', '.join(ex.competing)}", classes="ec-details")
        if ex.falsifiers:
            yield Static(f"  falsifiers: {'; '.join(ex.falsifiers)}", classes="ec-details")
