"""Tests for InvestigationScreen — INV-4-5, INV-4-6."""

from __future__ import annotations

import pytest

from thesean.tui.state import CaseState, ScreenMode, screen_mode_from_case_state


@pytest.mark.tui
class TestInvestigationScreenPrerequisites:

    def test_navigation_requires_ready_state(self) -> None:
        """INV-4-6: investigation requires workspace_loaded (READY state)."""
        ready_states = {CaseState.READY, CaseState.NEEDS_ATTENTION}
        for cs in CaseState:
            mode = screen_mode_from_case_state(cs)
            if cs in ready_states:
                assert mode == ScreenMode.READY_INVESTIGATION
            else:
                assert mode != ScreenMode.READY_INVESTIGATION or cs in ready_states
