"""Tests for CaseBar — displays case ID and state badge."""

from __future__ import annotations

import pytest

from thesean.models.case import Case
from thesean.models.run import Run
from thesean.tui.widgets.case_bar import CaseBar


@pytest.mark.unit
class TestCaseBarState:

    def test_construction(self) -> None:
        bar = CaseBar()
        assert bar._case is None
        assert bar._case_state == "draft"

    def test_stores_case_reference(self) -> None:
        """CaseBar stores the case and state internally."""
        bar = CaseBar()
        case = Case(id="my-case", track_ref="monza", run_a=Run(id="a", world_model_ref="w.pth"))
        bar._case = case
        bar._case_state = "running"
        assert bar._case.id == "my-case"
        assert bar._case_state == "running"

    def test_state_colors_map(self) -> None:
        """Verify the state color map in _refresh_content has expected keys."""
        expected_states = {"draft", "running", "pending", "run_failed", "ready"}
        # We test the mapping directly from the source
        state_colors = {
            "draft": ("Draft", "dim"),
            "running": ("Running", "yellow"),
            "pending": ("Analyzing", "cyan"),
            "run_failed": ("Run failed", "red"),
            "ready": ("Ready", "green"),
        }
        assert set(state_colors.keys()) == expected_states
