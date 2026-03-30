"""Tests for stage runner execution semantics — INV-3-*."""

from __future__ import annotations

import pytest

from thesean.pipeline.context import RunContext
from thesean.pipeline.runner import run_stages
from thesean.pipeline.state import StageResult

# ── Protocol-satisfying stubs (no mocks) ─────────────────────────────


class RecordingObserver:
    """Observer that records callback sequence."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def on_stage_start(self, name: str) -> None:
        self.calls.append(("start", name))

    def on_stage_complete(self, name: str, result: StageResult) -> None:
        self.calls.append(("complete", name))

    def on_stage_fail(self, name: str, error: str) -> None:
        self.calls.append(("fail", name))

    def on_stage_skip(self, name: str, reason: str) -> None:
        self.calls.append(("skip", name))

    def on_stage_reuse(self, name: str) -> None:
        self.calls.append(("reuse", name))


class DummyStage:
    """Minimal Stage satisfying the Stage protocol."""

    def __init__(
        self,
        name: str,
        requires: tuple[str, ...] = (),
        *,
        fail: bool = False,
        up_to_date: bool = False,
    ) -> None:
        self.name = name
        self.requires = requires
        self._fail = fail
        self._up_to_date = up_to_date
        self.ran = False

    def is_up_to_date(self, ctx: RunContext) -> bool:
        return self._up_to_date

    def run(self, ctx: RunContext) -> StageResult:
        self.ran = True
        if self._fail:
            raise RuntimeError(f"Stage {self.name} failed")
        return StageResult(summary=f"{self.name} done")


# ── Helpers ──────────────────────────────────────────────────────────

def _make_ctx(tmp_path, monkeypatch) -> RunContext:
    """Build minimal RunContext from temp workspace."""
    import tomli_w

    from thesean.models.case import Case
    from thesean.models.run import Run

    ws = tmp_path / "ws"
    ws.mkdir()

    with (ws / "thesean.toml").open("wb") as f:
        tomli_w.dump({"adapter": {"type": "dummy", "repo": str(tmp_path)}}, f)

    case = Case(
        id="test",
        run_a=Run(id="a", world_model_ref="w.pth"),
        run_b=Run(id="b", world_model_ref="w.pth"),
    )
    (ws / "case.json").write_text(case.model_dump_json())

    from tests.conftest import DummyAdapterFactory
    monkeypatch.setattr(
        "thesean.pipeline.context.load_adapter_factory",
        lambda name: DummyAdapterFactory(),
    )
    return RunContext(ws)


# ── Tests ────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestStageExecutionOrder:

    def test_stages_execute_in_declared_order(self, tmp_path, monkeypatch) -> None:
        """INV-3-1: stages execute in declared order."""
        ctx = _make_ctx(tmp_path, monkeypatch)
        obs = RecordingObserver()
        stages = (DummyStage("a"), DummyStage("b"), DummyStage("c"))
        run_stages(ctx, stages, observer=obs)
        started = [name for action, name in obs.calls if action == "start"]
        assert started == ["a", "b", "c"]


@pytest.mark.unit
class TestStageStateTransitions:

    def test_completed_stage_has_result_and_finished_at(self, tmp_path, monkeypatch) -> None:
        """INV-3-2: completed stage has non-None result and finished_at."""
        ctx = _make_ctx(tmp_path, monkeypatch)
        run_stages(ctx, (DummyStage("s1"),), observer=RecordingObserver())
        state = ctx.state.stages["s1"]
        assert state.status == "completed"
        assert state.result is not None
        assert state.finished_at is not None

    def test_failed_stage_has_error_and_finished_at(self, tmp_path, monkeypatch) -> None:
        """INV-3-3: failed stage has non-None error and finished_at."""
        ctx = _make_ctx(tmp_path, monkeypatch)
        with pytest.raises(RuntimeError):
            run_stages(ctx, (DummyStage("s1", fail=True),), observer=RecordingObserver())
        state = ctx.state.stages["s1"]
        assert state.status == "failed"
        assert state.error is not None
        assert state.finished_at is not None

    def test_failed_stage_saves_state_before_raise(self, tmp_path, monkeypatch) -> None:
        """INV-3-4: failed stage persists state before re-raising."""
        ctx = _make_ctx(tmp_path, monkeypatch)
        with pytest.raises(RuntimeError):
            run_stages(ctx, (DummyStage("s1", fail=True),), observer=RecordingObserver())
        # State file should exist on disk
        assert ctx.state_path.exists()


@pytest.mark.unit
class TestResumeMode:

    def test_resume_reuses_up_to_date_stages(self, tmp_path, monkeypatch) -> None:
        """INV-3-5: resume mode reuses up-to-date stages."""
        ctx = _make_ctx(tmp_path, monkeypatch)
        ctx.resume = True
        stage = DummyStage("s1", up_to_date=True)
        obs = RecordingObserver()
        run_stages(ctx, (stage,), observer=obs)
        assert not stage.ran
        assert ("reuse", "s1") in obs.calls


@pytest.mark.unit
class TestObserverCallbackOrder:

    def test_start_then_complete(self, tmp_path, monkeypatch) -> None:
        ctx = _make_ctx(tmp_path, monkeypatch)
        obs = RecordingObserver()
        run_stages(ctx, (DummyStage("s1"),), observer=obs)
        actions = [a for a, _ in obs.calls]
        assert actions == ["start", "complete"]

    def test_start_then_fail(self, tmp_path, monkeypatch) -> None:
        ctx = _make_ctx(tmp_path, monkeypatch)
        obs = RecordingObserver()
        with pytest.raises(RuntimeError):
            run_stages(ctx, (DummyStage("s1", fail=True),), observer=obs)
        actions = [a for a, _ in obs.calls]
        assert actions == ["start", "fail"]
