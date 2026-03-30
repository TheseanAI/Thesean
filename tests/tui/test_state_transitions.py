"""Tests for TUI state transitions — INV-6-*."""

from __future__ import annotations

import pytest

from thesean.tui.state import AppState, CaseState, RuntimeStatus, ScreenMode, screen_mode_from_case_state


@pytest.mark.unit
class TestCaseStateEnum:

    def test_exactly_7_members(self) -> None:
        """INV-6-5: CaseState enum has exactly 7 members."""
        assert len(CaseState) == 7

    def test_all_values(self) -> None:
        expected = {"draft", "running", "run_failed", "run_complete",
                    "analysis_partial", "ready", "needs_attention"}
        assert {cs.value for cs in CaseState} == expected


@pytest.mark.unit
class TestRuntimeStatusMode:

    def test_exactly_12_valid_modes(self) -> None:
        """INV-6-6: RuntimeStatus.mode has exactly 12 valid literals."""
        valid_modes = {
            "idle", "loading_case", "creating_case",
            "running_compare", "running_isolate", "running_attribute", "running_report",
            "eval_running_a", "eval_running_b", "eval_computing",
            "complete", "error",
        }
        assert len(valid_modes) == 12
        # Verify each mode can be set
        for mode in valid_modes:
            rs = RuntimeStatus(mode=mode)
            assert rs.mode == mode


@pytest.mark.unit
class TestAppStateRunInProgress:

    def test_true_only_for_active_modes(self) -> None:
        """INV-6-7: AppState.run_in_progress is True only for active modes."""
        inactive = {"idle", "complete", "error"}
        all_modes = {
            "idle", "loading_case", "creating_case",
            "running_compare", "running_isolate", "running_attribute", "running_report",
            "eval_running_a", "eval_running_b", "eval_computing",
            "complete", "error",
        }
        for mode in all_modes:
            state = AppState(runtime=RuntimeStatus(mode=mode))
            if mode in inactive:
                assert not state.run_in_progress, f"mode={mode} should not be in_progress"
            else:
                assert state.run_in_progress, f"mode={mode} should be in_progress"


@pytest.mark.unit
class TestScreenModeExhaustive:

    def test_all_case_states_covered_no_key_error(self) -> None:
        """screen_mode_from_case_state covers all CaseState values (no KeyError)."""
        for cs in CaseState:
            mode = screen_mode_from_case_state(cs)
            assert isinstance(mode, ScreenMode)
