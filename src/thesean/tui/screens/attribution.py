"""Attribution Workspace Screen — tier-aware explanation presentation."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from thesean.models.case import Case
from thesean.models.event import Event
from thesean.models.explanation import Explanation
from thesean.models.isolation import AttributionTable
from thesean.tui.widgets.causal_sequence import CausalSequence
from thesean.tui.widgets.explanation_card import ExplanationCard
from thesean.tui.widgets.falsifier_list import FalsifierList
from thesean.tui.widgets.tier_indicator import TierIndicator


class AttributionWorkspaceScreen(Screen):
    """Presents tier-aware Explanations for detected events."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("i", "investigation", "Investigation", show=True),
        Binding("I", "run_isolation", "Run isolation", show=True),
    ]

    DEFAULT_CSS = """
    AttributionWorkspaceScreen {
        layout: vertical;
    }
    AttributionWorkspaceScreen #attr-header {
        height: 3;
        padding: 1;
        background: $boost;
        text-style: bold;
    }
    AttributionWorkspaceScreen #attr-main {
        height: 1fr;
    }
    AttributionWorkspaceScreen #attr-explanations {
        width: 1fr;
        padding: 1;
    }
    AttributionWorkspaceScreen #attr-sidebar {
        width: 35;
        padding: 1;
    }
    AttributionWorkspaceScreen #attr-actions {
        height: 3;
        padding: 0 1;
    }
    AttributionWorkspaceScreen #attr-actions Button {
        margin: 0 1;
    }
    AttributionWorkspaceScreen #attr-why-outranks {
        padding: 1;
        background: $panel;
        margin: 1 0;
    }
    AttributionWorkspaceScreen #attr-counterfactual {
        padding: 1;
        margin: 1 0;
        border: solid $panel;
    }
    """

    def __init__(
        self,
        events: list[Event] | None = None,
        explanations: list[Explanation] | None = None,
        tier: str = "tier_0",
        case: Case | None = None,
        attributions: list[AttributionTable] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._events = events or []
        self._explanations = explanations or []
        self._tier = tier
        self._case = case
        self._attributions = attributions or []

    def compose(self) -> ComposeResult:
        yield Header()

        # Title bar
        if self._events:
            evt = self._events[0]
            yield Static(
                f"ATTRIBUTION - Event {evt.step} - {self._tier.replace('_', ' ').title()}",
                id="attr-header",
            )
        else:
            yield Static("ATTRIBUTION - No events", id="attr-header")

        yield TierIndicator(id="attr-tier")

        with Horizontal(id="attr-main"):
            # Main: explanations
            with VerticalScroll(id="attr-explanations"):
                if self._explanations:
                    # Best explanation highlighted
                    yield Static("Best explanation:", classes="section-title")
                    yield ExplanationCard(self._explanations[0], rank=1)

                    # Why #1 outranks section
                    yield Static(
                        self._build_why_outranks(),
                        id="attr-why-outranks",
                    )

                    if len(self._explanations) > 1:
                        yield Static("Competing:", classes="section-title")
                        for i, ex in enumerate(self._explanations[1:], 2):
                            yield ExplanationCard(ex, rank=i)
                else:
                    yield Static(
                        "No explanations available.\n"
                        "Run the full pipeline (compare + isolate + attribute) to generate explanations."
                    )

                # Counterfactual evidence table
                yield Static(
                    self._build_counterfactual_table(),
                    id="attr-counterfactual",
                )

                yield CausalSequence(id="attr-causal")

            # Sidebar
            with Vertical(id="attr-sidebar"):
                yield FalsifierList()

        # Actions
        with Horizontal(id="attr-actions"):
            yield Button("Evidence", id="attr-evidence")
            yield Button("Run Isolation", id="attr-run-isolation")
            yield Button("Export", id="attr-export")
            yield Button("Back to investigation", id="attr-back", variant="primary")

        yield Footer()

    def _build_why_outranks(self) -> str:
        """Build the 'Why #1 outranks' narrative section."""
        if not self._explanations:
            return ""

        best = self._explanations[0]
        lines = ["Why this explanation outranks others:"]
        lines.append(f"  Confidence: {best.confidence:.1%}")

        if best.support_basis:
            lines.append(f"  Support: {', '.join(best.support_basis[:4])}")

        if len(self._explanations) > 1:
            runner_up = self._explanations[1]
            gap = best.confidence - runner_up.confidence
            lines.append(f"  Margin over #{2}: {gap:+.1%} ({runner_up.label})")

        if best.falsifiers:
            lines.append(f"  Unfalsified ({len(best.falsifiers)} tests passed)")
        else:
            lines.append("  No falsification tests available")

        if best.tier != "tier_0":
            lines.append(f"  Backed by {best.tier.replace('_', ' ')} isolation evidence")

        return "\n".join(lines)

    def _build_counterfactual_table(self) -> str:
        """Build the counterfactual evidence table."""
        if not self._explanations:
            return "Counterfactual Evidence\n  No data — run isolation pipeline"

        lines = ["Counterfactual Evidence Table"]
        lines.append(f"  {'Component':<12} {'Changed?':<10} {'Effect on gap':<16} {'Confidence'}")
        lines.append("  " + "-" * 52)

        # Build from support_basis of top explanation
        best = self._explanations[0]
        components = ["Encoder", "World Model", "Planner"]
        for comp in components:
            comp_key = comp.lower().replace(" ", "_")
            is_factor = any(comp_key in s.lower() or comp[:3].lower() in s.lower()
                           for s in best.support_basis)
            changed = "YES" if is_factor else "no"
            effect = "REDUCES" if is_factor else "unchanged"
            conf = f"{best.confidence:.0%}" if is_factor else "-"
            lines.append(f"  {comp:<12} {changed:<10} {effect:<16} {conf}")

        if not best.support_basis:
            lines.append("  (Run isolation pipeline for counterfactual data)")

        return "\n".join(lines)

    def on_mount(self) -> None:
        tier_widget = self.query_one(TierIndicator)
        tier_widget.set_tier(self._tier)

        # Only show Run Isolation button at tier_0 (no isolation data yet)
        try:
            iso_btn = self.query_one("#attr-run-isolation", Button)
            iso_btn.display = self._tier == "tier_0"
        except Exception:
            pass

        causal = self.query_one(CausalSequence)
        causal.set_events(self._events)

        # Pass factor chain from first attribution table
        if self._attributions:
            causal.set_factor_chain(self._attributions[0].main_effects)

        falsifiers = self.query_one(FalsifierList)
        all_falsifiers: list[str] = []
        for ex in self._explanations:
            all_falsifiers.extend(ex.falsifiers)
        falsifiers.set_falsifiers(all_falsifiers)

        # Pass interaction effects as falsifiers if available
        if self._attributions:
            all_interactions = []
            for attr in self._attributions:
                all_interactions.extend(attr.interaction_effects)
            if all_interactions:
                falsifiers.set_interaction_effects(all_interactions)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "attr-back":
            self.app.pop_screen()
        elif event.button.id == "attr-evidence":
            from thesean.tui.screens.drawers.evidence_drawer import EvidenceDrawer
            self.app.push_screen(EvidenceDrawer(events=self._events))
        elif event.button.id == "attr-run-isolation":
            self.action_run_isolation()
        elif event.button.id == "attr-export":
            self.notify("Export: use 'thesean report' CLI to generate HTML/JSON")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_run_isolation(self) -> None:
        if hasattr(self.app, "run_isolation"):
            self.app.run_isolation()

    def action_investigation(self) -> None:
        self.app.pop_screen()
