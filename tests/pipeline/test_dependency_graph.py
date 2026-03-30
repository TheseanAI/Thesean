"""Tests for pipeline dependency graph — INV-3-5 prereqs."""

from __future__ import annotations

import pytest
import tomli_w

from thesean.models.case import Case
from thesean.models.run import Run
from thesean.pipeline.context import RunContext
from thesean.pipeline.runner import run_stages
from thesean.pipeline.state import StageResult, StageState
from tests.conftest import DummyAdapterFactory


def _make_ctx(tmp_path, monkeypatch, **kw) -> RunContext:
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    with (ws / "thesean.toml").open("wb") as f:
        tomli_w.dump({"adapter": {"type": "dummy", "repo": str(tmp_path)}}, f)
    case = Case(
        id="test",
        run_a=Run(id="a", world_model_ref="w.pth"),
        run_b=Run(id="b", world_model_ref="w.pth"),
    )
    (ws / "case.json").write_text(case.model_dump_json())
    monkeypatch.setattr(
        "thesean.pipeline.context.load_adapter_factory",
        lambda name: DummyAdapterFactory(),
    )
    return RunContext(ws, **kw)


class _DummyStage:
    def __init__(self, name: str, requires: tuple[str, ...] = ()) -> None:
        self.name = name
        self.requires = requires

    def is_up_to_date(self, ctx: RunContext) -> bool:
        return False

    def run(self, ctx: RunContext) -> StageResult:
        return StageResult(summary=f"{self.name} done")


@pytest.mark.unit
class TestPrereqsSatisfied:

    def test_missing_prereq_returns_false(self, tmp_path, monkeypatch) -> None:
        """INV-3-5: prereqs_satisfied returns False for missing prereqs."""
        ctx = _make_ctx(tmp_path, monkeypatch)
        assert ctx.prereqs_satisfied(("nonexistent",)) is False

    def test_skipped_prereq_returns_false(self, tmp_path, monkeypatch) -> None:
        ctx = _make_ctx(tmp_path, monkeypatch)
        ctx.state.stages["dep"] = StageState(name="dep", status="skipped")
        assert ctx.prereqs_satisfied(("dep",)) is False

    def test_failed_prereq_returns_false(self, tmp_path, monkeypatch) -> None:
        ctx = _make_ctx(tmp_path, monkeypatch)
        ctx.state.stages["dep"] = StageState(name="dep", status="failed", error="boom")
        assert ctx.prereqs_satisfied(("dep",)) is False

    def test_completed_prereq_returns_true(self, tmp_path, monkeypatch) -> None:
        ctx = _make_ctx(tmp_path, monkeypatch)
        ctx.state.stages["dep"] = StageState(name="dep", status="completed")
        assert ctx.prereqs_satisfied(("dep",)) is True

    def test_empty_requires_always_passes(self, tmp_path, monkeypatch) -> None:
        ctx = _make_ctx(tmp_path, monkeypatch)
        assert ctx.prereqs_satisfied(()) is True


@pytest.mark.unit
class TestDependencyViolation:

    def test_unmet_dependency_raises(self, tmp_path, monkeypatch) -> None:
        """Dependency violation raises RuntimeError."""
        ctx = _make_ctx(tmp_path, monkeypatch)
        stage = _DummyStage("child", requires=("parent",))
        with pytest.raises(RuntimeError, match="requires completed stages"):
            run_stages(ctx, (stage,), observer=None)
