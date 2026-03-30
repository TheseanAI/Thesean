"""Transport bar — step scrubber and event navigation controls."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, ProgressBar, Static


class TransportBar(Vertical):
    """Bottom transport bar — single row with step controls and event nav."""

    current_step: reactive[int] = reactive(0)
    max_step: reactive[int] = reactive(0)

    class StepChanged(Message):
        def __init__(self, step: int) -> None:
            self.step = step
            super().__init__()

    class EventSelected(Message):
        def __init__(self, event_idx: int) -> None:
            self.event_idx = event_idx
            super().__init__()

    class EpisodeNav(Message):
        def __init__(self, direction: int) -> None:
            self.direction = direction
            super().__init__()

    class CycleRequested(Message):
        def __init__(self, target: str) -> None:
            self.target = target
            super().__init__()

    DEFAULT_CSS = """
    TransportBar {
        height: auto;
        background: $boost;
        dock: bottom;
        border-top: hkey $panel;
    }
    TransportBar Horizontal {
        height: 3;
        padding: 0 1;
        align: left middle;
    }
    TransportBar .tb-label {
        width: auto;
        padding: 0 1;
    }
    TransportBar #tb-episode-label {
        width: auto;
        text-style: bold;
        padding: 0 1;
        color: $accent;
    }
    TransportBar .tb-step {
        width: auto;
        text-style: bold;
        padding: 0 1;
    }
    TransportBar ProgressBar {
        width: 1fr;
        padding: 0 1;
    }
    TransportBar Button {
        min-width: 3;
        height: 1;
        margin: 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="tb-row-1"):
            yield Button("<Ep", id="tb-prev-episode")
            yield Static("", id="tb-episode-label", classes="tb-label")
            yield Button("Ep>", id="tb-next-episode")
            yield Button("<<", id="tb-step-back-10")
            yield Button("<", id="tb-prev-step")
            yield Static("t=0", id="tb-step-display", classes="tb-step")
            yield Button(">", id="tb-next-step")
            yield Button(">>", id="tb-step-fwd-10")
            yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="tb-progress")
            yield Static("", id="tb-range", classes="tb-label")
            yield Button("[", id="tb-prev-event")
            yield Button("]", id="tb-next-event")

    def watch_current_step(self, step: int) -> None:
        try:
            display = self.query_one("#tb-step-display", Static)
        except Exception:
            return
        display.update(f"Step {step}")
        if self.max_step > 0:
            progress = self.query_one("#tb-progress", ProgressBar)
            progress.update(total=self.max_step, progress=step)

    def watch_max_step(self, value: int) -> None:
        try:
            label = self.query_one("#tb-range", Static)
        except Exception:
            return
        label.update(f"/{value}")

    def update_episode_label(self, episode_num: int, episode_total: int) -> None:
        """Update the persistent episode label (D-04)."""
        label = self.query_one("#tb-episode-label", Static)
        label.update(f"Ep {episode_num}/{episode_total}")

    def update_cycle_label(self, target: str, text: str) -> None:
        """No-op — cycling buttons moved to ActionBar."""
        pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "tb-prev-step":
            self.step_backward()
        elif bid == "tb-next-step":
            self.step_forward()
        elif bid == "tb-step-back-10":
            self.step_backward(10)
        elif bid == "tb-step-fwd-10":
            self.step_forward(10)
        elif bid == "tb-prev-event":
            self.post_message(self.EventSelected(-1))
        elif bid == "tb-next-event":
            self.post_message(self.EventSelected(1))
        elif bid == "tb-prev-episode":
            self.post_message(self.EpisodeNav(-1))
        elif bid == "tb-next-episode":
            self.post_message(self.EpisodeNav(1))

    def step_forward(self, amount: int = 1) -> None:
        new = min(self.current_step + amount, self.max_step)
        if new != self.current_step:
            self.current_step = new
            self.post_message(self.StepChanged(new))

    def step_backward(self, amount: int = 1) -> None:
        new = max(self.current_step - amount, 0)
        if new != self.current_step:
            self.current_step = new
            self.post_message(self.StepChanged(new))

    def goto_step(self, step: int) -> None:
        step = max(0, min(step, self.max_step))
        if step != self.current_step:
            self.current_step = step
            self.post_message(self.StepChanged(step))
