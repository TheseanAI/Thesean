"""Per-run configuration panel for the Run Builder."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Select, Static


class RunConfigPanel(Vertical):
    """Configuration panel for a single run (A or B)."""

    class ConfigChanged(Message):
        def __init__(self, panel_id: str, field: str, value: Any) -> None:
            self.panel_id = panel_id
            self.field = field
            self.value = value
            super().__init__()

    DEFAULT_CSS = """
    RunConfigPanel {
        width: 1fr;
        height: auto;
        padding: 1 1;
        border: round $panel;
        border-title-color: $primary;
        border-title-style: bold;
        background: transparent;
    }
    RunConfigPanel:focus-within {
        border: round $primary;
    }
    RunConfigPanel .rcp-field-label {
        color: $text-muted;
        margin: 0;
        padding: 0 1;
    }
    RunConfigPanel Select {
        width: 100%;
        height: 3;
        margin: 0;
    }
    RunConfigPanel .rcp-model-fields {
        height: auto;
        margin-bottom: 0;
    }
    RunConfigPanel #planner_btn {
        margin: 1 0 0 0;
        width: 100%;
        background: transparent;
        color: $text-muted;
        border: none;
        height: 1;
        text-style: italic;
    }
    RunConfigPanel #planner_btn:hover {
        color: $primary;
        text-style: bold;
        background: transparent;
    }
    """

    def __init__(
        self,
        label: str,
        panel_id: str,
        weights: list[dict[str, Any]] | None = None,
        envs: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._panel_id = panel_id
        self._weights = weights or []
        self._envs = envs or []
        self.planner_config = {
            "horizon": 25,
            "num_candidates": 400,
            "iterations": 4,
            "num_elites": 40,
            "seed": 42,
        }

    def compose(self) -> ComposeResult:
        self.border_title = self._label

        # Model fields
        weight_options = [(w["name"], w.get("path", w["name"])) for w in self._weights]
        with Vertical(classes="rcp-model-fields"):
            yield Static("Model Checkpoints", classes="rcp-field-label")
            yield Select(
                weight_options,
                id=f"{self._panel_id}_weight",
                allow_blank=True,
            )

        # Planner settings button (to open modal)
        yield Button("Planner Settings ▾", id="planner_btn")

    def on_select_changed(self, event: Select.Changed) -> None:
        select_id = str(event.select.id or "")
        field = select_id.replace(f"{self._panel_id}_", "")
        self.post_message(self.ConfigChanged(self._panel_id, field, event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "planner_btn":
            # This is handled by the parent screen (RunBuilderScreen)
            pass

    def set_weight(self, weight_path: str) -> None:
        """Set the weight Select to the given path value."""
        sel = self.query_one(f"#{self._panel_id}_weight", Select)
        try:
            sel.value = weight_path
        except Exception:
            sel.value = Select.BLANK

    def set_planner_config(self, config: dict[str, Any]) -> None:
        """Update local config dictionary."""
        self.planner_config.update(config)

    def set_seed(self, seed: int) -> None:
        """Set the seed value."""
        self.planner_config["seed"] = seed

    @property
    def selected_weight(self) -> str | None:
        sel = self.query_one(f"#{self._panel_id}_weight", Select)
        if sel.value is not None and sel.value != Select.BLANK:
            return str(sel.value)
        return None

    @property
    def selected_planner(self) -> str:
        return "cem"

    @property
    def selected_planning_horizon(self) -> int:
        return self.planner_config.get("horizon", 25)

    @property
    def selected_num_candidates(self) -> int:
        return self.planner_config.get("num_candidates", 400)

    @property
    def selected_iterations(self) -> int:
        return self.planner_config.get("iterations", 4)

    @property
    def selected_num_elites(self) -> int:
        return self.planner_config.get("num_elites", 40)

    @property
    def selected_seed(self) -> int:
        return self.planner_config.get("seed", 42)

    @property
    def planner_config_dict(self) -> dict[str, int]:
        """Return planner config dict without runner-level keys like seed."""
        return {k: v for k, v in self.planner_config.items() if k != "seed"}
