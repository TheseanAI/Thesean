"""Tests for screen mode transitions — pure function, no Textual runtime."""

from __future__ import annotations

import pytest

from thesean.tui.state import CaseState, RuntimeStatus, ScreenMode, screen_mode_from_case_state


@pytest.mark.unit
class TestScreenModeFromCaseState:

    def test_draft_maps_to_draft_empty(self) -> None:
        assert screen_mode_from_case_state(CaseState.DRAFT) == ScreenMode.DRAFT_EMPTY

    def test_running_maps_to_running_live(self) -> None:
        assert screen_mode_from_case_state(CaseState.RUNNING) == ScreenMode.RUNNING_LIVE

    def test_run_failed_maps_to_draft_empty(self) -> None:
        assert screen_mode_from_case_state(CaseState.RUN_FAILED) == ScreenMode.DRAFT_EMPTY

    def test_run_complete_maps_to_running_live(self) -> None:
        """Analysis still pending after run completes."""
        assert screen_mode_from_case_state(CaseState.RUN_COMPLETE) == ScreenMode.RUNNING_LIVE

    def test_analysis_partial_maps_to_analysis_failed(self) -> None:
        assert screen_mode_from_case_state(CaseState.ANALYSIS_PARTIAL) == ScreenMode.ANALYSIS_FAILED

    def test_ready_maps_to_ready_investigation(self) -> None:
        assert screen_mode_from_case_state(CaseState.READY) == ScreenMode.READY_INVESTIGATION

    def test_needs_attention_maps_to_ready_investigation(self) -> None:
        assert screen_mode_from_case_state(CaseState.NEEDS_ATTENTION) == ScreenMode.READY_INVESTIGATION

    def test_exhaustive_all_case_states_covered(self) -> None:
        """INV-4-5: mapping is exhaustive — all 7 CaseState values produce a ScreenMode."""
        for cs in CaseState:
            result = screen_mode_from_case_state(cs)
            assert isinstance(result, ScreenMode), f"CaseState.{cs.name} not covered"


@pytest.mark.unit
class TestRuntimeStatusRunInProgress:

    def test_idle_not_in_progress(self) -> None:
        """INV-4-3: run_in_progress is False for idle."""
        rs = RuntimeStatus(mode="idle")
        from thesean.tui.state import AppState
        state = AppState(runtime=rs)
        assert state.run_in_progress is False

    def test_complete_not_in_progress(self) -> None:
        rs = RuntimeStatus(mode="complete")
        from thesean.tui.state import AppState
        state = AppState(runtime=rs)
        assert state.run_in_progress is False

    def test_error_not_in_progress(self) -> None:
        rs = RuntimeStatus(mode="error")
        from thesean.tui.state import AppState
        state = AppState(runtime=rs)
        assert state.run_in_progress is False

    def test_running_modes_are_in_progress(self) -> None:
        """All active modes should show run_in_progress=True."""
        from thesean.tui.state import AppState
        active_modes = [
            "loading_case", "creating_case",
            "running_compare", "running_isolate", "running_attribute", "running_report",
            "eval_running_a", "eval_running_b", "eval_computing",
        ]
        for mode in active_modes:
            rs = RuntimeStatus(mode=mode)
            state = AppState(runtime=rs)
            assert state.run_in_progress is True, f"mode={mode} should be in_progress"
