"""Tests for stage state model semantics."""

from __future__ import annotations

from thesean.pipeline.state import RunState, StageResult, StageState


class TestStageState:
    def test_default_status_is_pending(self) -> None:
        s = StageState(name="compare")
        assert s.status == "pending"
        assert s.reused is False

    def test_reused_flag(self) -> None:
        s = StageState(name="compare", status="completed", reused=True)
        assert s.reused is True

    def test_result_optional(self) -> None:
        s = StageState(name="compare", status="completed")
        assert s.result is None


class TestStageResult:
    def test_defaults(self) -> None:
        r = StageResult()
        assert r.primary_output is None
        assert r.output_paths == []
        assert r.summary is None
        assert r.warnings == []
        assert r.metadata == {}

    def test_with_values(self) -> None:
        r = StageResult(
            primary_output="/tmp/out.json",
            output_paths=["/tmp/out.json", "/tmp/compare_report.json"],
            summary="5 findings, 2 regressions",
            warnings=["swap_wm failed"],
            metadata={"num_findings": 5, "num_regressions": 2},
        )
        assert r.primary_output == "/tmp/out.json"
        assert len(r.output_paths) == 2
        assert r.metadata["num_findings"] == 5


class TestRunState:
    def test_empty_state(self) -> None:
        state = RunState()
        assert state.stages == {}

    def test_dict_keyed_by_name(self) -> None:
        state = RunState()
        state.stages["compare"] = StageState(name="compare", status="completed")
        state.stages["isolate"] = StageState(name="isolate", status="pending")
        assert state.stages["compare"].status == "completed"
        assert state.stages["isolate"].status == "pending"

    def test_json_round_trip(self) -> None:
        state = RunState()
        state.stages["compare"] = StageState(
            name="compare",
            status="completed",
            result=StageResult(summary="done"),
            reused=True,
        )
        json_str = state.model_dump_json()
        loaded = RunState.model_validate_json(json_str)
        assert loaded.stages["compare"].status == "completed"
        assert loaded.stages["compare"].reused is True
        assert loaded.stages["compare"].result.summary == "done"
