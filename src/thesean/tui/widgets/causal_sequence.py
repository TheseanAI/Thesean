"""Causal sequence — event chain timeline and factor attribution visualization."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from thesean.models.event import Event
from thesean.models.isolation import EffectEstimate

_TYPE_SHORT = {
    "first_signal_divergence": "sig div",
    "first_action_divergence": "act div",
    "first_risk_spike": "risk",
    "first_boundary_collapse": "boundary",
    "terminal": "terminal",
    "max_metric_gap": "max gap",
}

_FACTOR_STYLES = {
    "world_model": "bold magenta",
    "planner": "bold cyan",
    "env": "bold green",
    "interaction": "bold yellow",
    "unknown": "dim",
}


class CausalSequence(Static):
    """Displays event chain as a causal arrow sequence, plus factor attribution chain."""

    DEFAULT_CSS = """
    CausalSequence {
        height: auto;
        padding: 1;
    }
    """

    def set_events(self, events: list[Event]) -> None:
        """Set the event chain (temporal causal sequence)."""
        if not events:
            self.update("No causal sequence available")
            return
        text = Text()
        text.append("Event chain: ", style="bold")
        for i, evt in enumerate(events):
            if i > 0:
                text.append(" -> ", style="dim")
            label = _TYPE_SHORT.get(evt.type, evt.type)
            text.append(f"[{evt.step}]", style="bold")
            text.append(label)
        self.update(text)

    def set_factor_chain(self, main_effects: list[EffectEstimate]) -> None:
        """Set the factor attribution chain from isolation results."""
        if not main_effects:
            return

        # Sort by effect magnitude descending
        sorted_effects = sorted(main_effects, key=lambda e: abs(e.effect), reverse=True)

        text = Text()
        text.append("\nFactor attribution: ", style="bold")
        for i, eff in enumerate(sorted_effects):
            if i > 0:
                text.append(" > ", style="dim")
            style = _FACTOR_STYLES.get(eff.factor, "")
            conf_pct = f"{eff.confidence:.0%}" if eff.confidence else "?"
            text.append(f"{eff.factor}", style=style)
            text.append(f"({conf_pct})", style="dim")

        self.update(text)
