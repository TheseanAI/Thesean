"""Case History modal — browse and open previous cases."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option


def _short(ref: str) -> str:
    if not ref:
        return ""
    parts = ref.replace("\\", "/").split("/")
    return parts[-1] if parts else ref


class CaseHistoryModal(ModalScreen[Path | None]):
    DEFAULT_CSS = """
    CaseHistoryModal {
        align: center middle;
    }
    CaseHistoryModal > Vertical {
        width: 80;
        height: auto;
        max-height: 25;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    CaseHistoryModal #ch-title {
        text-style: bold;
        padding-bottom: 1;
    }
    CaseHistoryModal OptionList {
        height: auto;
        max-height: 15;
        margin-bottom: 1;
    }
    CaseHistoryModal #ch-empty {
        padding: 1;
        margin-bottom: 1;
    }
    CaseHistoryModal Horizontal {
        height: auto;
        align-horizontal: right;
    }
    CaseHistoryModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, cases: list[Path], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cases = cases

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Case History", id="ch-title")
            if self._cases:
                option_list = OptionList(id="ch-list")
                for case_path in self._cases:
                    label = self._format_case(case_path)
                    option_list.add_option(Option(label, id=str(case_path)))
                yield option_list
                with Horizontal():
                    yield Button("Cancel", id="ch-cancel")
                    yield Button("Open", id="ch-open", variant="primary")
            else:
                yield Static(
                    "No previous cases found.\n"
                    'Use "Build Case" to create your first investigation.',
                    id="ch-empty",
                )
                with Horizontal():
                    yield Button("Close", id="ch-cancel")

    def _format_case(self, case_path: Path) -> str:
        """Build a display line from case directory metadata."""
        name = case_path.name
        track = ""
        checkpoint = ""

        try:
            from psystack.pipeline.case_io import load_case

            case = load_case(case_path)
            if case:
                track = case.track_ref or ""
                if case.run_a:
                    checkpoint = _short(case.run_a.world_model_ref)
        except Exception:
            pass

        try:
            mtime = case_path.stat().st_mtime
            date_str = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M"
            )
        except OSError:
            date_str = ""

        parts = [name]
        if track:
            parts.append(track)
        if checkpoint:
            parts.append(checkpoint)
        if date_str:
            parts.append(date_str)
        return "   ".join(parts)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ch-open":
            option_list = self.query_one("#ch-list", OptionList)
            idx = option_list.highlighted
            if idx is not None:
                option = option_list.get_option_at_index(idx)
                if option.id:
                    self.dismiss(Path(option.id))
                    return
            self.dismiss(None)
        elif event.button.id == "ch-cancel":
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.dismiss(Path(event.option.id))
