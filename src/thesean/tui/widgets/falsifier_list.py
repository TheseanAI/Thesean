"""Falsifier list — conditions that would disprove the explanation."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from thesean.models.isolation import EffectEstimate


class FalsifierList(Vertical):
    """Displays falsification conditions for the current explanation."""

    DEFAULT_CSS = """
    FalsifierList {
        height: auto;
        border: solid $panel;
        padding: 1;
    }
    FalsifierList .fl-title {
        text-style: bold;
        padding-bottom: 1;
    }
    FalsifierList .fl-item {
        color: $text-muted;
        padding: 0 0 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Falsifiers", classes="fl-title")
        yield Static("No falsifiers defined", id="fl-content", classes="fl-item")

    def set_falsifiers(self, falsifiers: list[str]) -> None:
        """Set falsifier conditions from explanation model."""
        content = self.query_one("#fl-content", Static)
        if not falsifiers:
            content.update("No falsifiers defined")
            return
        lines = [f"? {f}" for f in falsifiers]
        content.update("\n".join(lines))

    def set_interaction_effects(self, interactions: list[EffectEstimate]) -> None:
        """Set falsifiers derived from interaction effects (contradictions)."""
        content = self.query_one("#fl-content", Static)
        if not interactions:
            return

        text = Text()
        text.append("Interaction effects (potential contradictions):\n", style="bold")
        for eff in interactions:
            # An interaction effect suggests the main-effect attribution
            # may be incomplete — the factors interact non-additively
            severity = "HIGH" if abs(eff.effect) > 0.1 else "low"
            style = "bold red" if severity == "HIGH" else "dim"
            text.append(f"  [{severity}] ", style=style)
            text.append(f"{eff.factor}: effect={eff.effect:.4f}")
            if eff.confidence:
                text.append(f" (conf={eff.confidence:.0%})")
            text.append("\n")

        # If main factors explain <80% of total, add a falsifier note
        text.append("\nFalsification conditions:\n", style="bold")
        for eff in interactions:
            text.append(
                f"  ? If {eff.factor} effect persists after controlling main factors, "
                f"attribution is incomplete\n"
            )

        content.update(text)
