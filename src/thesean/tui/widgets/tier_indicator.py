"""Tier indicator — displays attribution tier with visual differentiation."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

_TIER_MESSAGES = {
    "tier_0": "Correlational only — no component isolation performed",
    "tier_1": "Component-isolated — swap tests narrow the cause",
    "tier_2": "Counterfactual — cross-validated with swap experiments",
    "tier_3": "Mechanistic — causal chain fully traced",
}

_TIER_STYLES = {
    "tier_0": ("bold red", "T0"),
    "tier_1": ("bold yellow", "T1"),
    "tier_2": ("bold green", "T2"),
    "tier_3": ("bold cyan", "T3"),
}


class TierIndicator(Static):
    """Shows the current attribution tier with colored badge and context."""

    DEFAULT_CSS = """
    TierIndicator {
        height: auto;
        padding: 1;
        background: $boost;
    }
    """

    def set_tier(self, tier: str) -> None:
        msg = _TIER_MESSAGES.get(tier, f"Unknown tier: {tier}")
        style, badge = _TIER_STYLES.get(tier, ("bold", "T?"))
        label = tier.replace("_", " ").title()

        text = Text()
        text.append(f" {badge} ", style=f"{style} reverse")
        text.append(f" {label}: ", style="bold")
        text.append(msg)
        self.update(text)
