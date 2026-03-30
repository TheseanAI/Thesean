"""Step inspector — shows A/B values at the current step with delta highlighting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

if TYPE_CHECKING:
    from thesean.core.signal_schema import SignalSchema

from thesean.models.event import Event


class StepInspector(Vertical):
    """Bottom-right panel showing per-step A/B signal values with delta highlighting."""

    DEFAULT_CSS = """
    StepInspector {
        width: 100%;
        height: 1fr;
        border: round $panel;
        padding: 1 1;
    }
    StepInspector .si-content {
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._schema: SignalSchema | None = None

    def compose(self) -> ComposeResult:
        self.border_title = "Step Inspector"
        yield Static("Select a step to inspect", id="si-content", classes="si-content")

    def set_schema(self, schema: SignalSchema | None) -> None:
        self._schema = schema

    def update_step(
        self,
        step: int,
        signals_a: dict[str, float] | None = None,
        signals_b: dict[str, float] | None = None,
        event: Event | None = None,
        hypothesis: str | None = None,
    ) -> None:
        content = self.query_one("#si-content", Static)
        text = Text()
        text.append(f"step {step}", style="bold")
        text.append("\n")

        # Show event info first if present (most important context)
        if event:
            text.append(event.type.replace("_", " "), style="")
            text.append(f"  score={event.score:.3f}\n", style="dim")

        # Signal deltas with directional arrows
        if signals_a and signals_b:
            keys: list[str] = []
            if self._schema:
                for group_name in self._schema.group_order:
                    for sig_def in self._schema.groups.get(group_name, []):
                        keys.append(sig_def.name)
                schema_keys = set(self._schema.signal_names())
                extra = sorted(set(signals_a.keys()) | set(signals_b.keys()) - schema_keys)
                keys.extend(extra)
            else:
                keys = sorted(set(signals_a) | set(signals_b))

            for key in keys:
                va = signals_a.get(key, 0.0)
                vb = signals_b.get(key, 0.0)
                delta = vb - va
                threshold = 0.1
                if self._schema:
                    sig_def_found = self._schema.get_def(key)
                    if sig_def_found:
                        threshold = sig_def_found.delta_threshold

                display_key = key[:10]
                text.append(f"{display_key:10s} ", style="dim")

                if abs(delta) > threshold:
                    arrow = "\u2191" if delta > 0 else "\u2193"
                    sign = "+" if delta >= 0 else ""
                    text.append(f"{arrow} {sign}{delta:.3f}", style="bold red")
                elif abs(delta) > threshold * 0.5:
                    arrow = "\u2191" if delta > 0 else "\u2193"
                    sign = "+" if delta >= 0 else ""
                    text.append(f"{arrow} {sign}{delta:.3f}", style="yellow")
                else:
                    sign = "+" if delta >= 0 else ""
                    text.append(f"  {sign}{delta:.3f}", style="dim")
                text.append("\n")

        if hypothesis:
            text.append("\n")
            text.append(f"\u2192 {hypothesis}\n", style="italic")

        content.update(text)
