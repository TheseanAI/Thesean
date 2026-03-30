"""Tests for RunContext state transition semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from thesean.models.case import Case
from thesean.models.run import Run
from thesean.pipeline.context import RunContext
from thesean.pipeline.state import StageResult, StageState


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Create a minimal valid workspace with thesean.toml and manifests."""
    import tomli_w

    from thesean.models import RunManifest

    repo = tmp_path / "fake-f1-repo"
    repo.mkdir()
    (repo / "checkpoints").mkdir()
    (repo / "tracks").mkdir()
    weights = str(repo / "checkpoints" / "world_model_v1.pth")
    env_config = {
        "track_csv": str(repo / "tracks" / "Monza.csv"),
        "max_speed": 50.0, "dt": 0.1, "max_steps": 200,
        "max_steer_rate": 3.5, "off_track_tolerance": 10,
        "raster_size": 64, "pixels_per_meter": 3.0,
        "progress_reward": 0.02, "off_track_penalty": 0.5,
        "step_penalty": 0.005, "lap_bonus": 1.0,
    }
    planner = {"num_candidates": 200, "horizon": 10, "iterations": 3, "num_elites": 20}

    with (tmp_path / "thesean.toml").open("wb") as f:
        tomli_w.dump({"adapter": {"type": "f1", "repo": str(repo)}}, f)

    b = RunManifest(run_id="baseline", world_model_weights=weights,
                    planner_config=planner, env_config=env_config, num_episodes=1, seed=42)
    c = RunManifest(run_id="candidate", world_model_weights=weights,
                    planner_config=planner, env_config=env_config, num_episodes=1, seed=42)

    (tmp_path / "baseline_manifest.json").write_text(b.model_dump_json(indent=2))
    (tmp_path / "candidate_manifest.json").write_text(c.model_dump_json(indent=2))

    # case.json — required by RunContext
    case = Case(
        id="test-case",
        track_ref="Monza",
        episode_count=1,
        run_a=Run(id="baseline", world_model_ref=weights, planner_config=planner, env_config=env_config, seed=42),
        run_b=Run(id="candidate", world_model_ref=weights, planner_config=planner, env_config=env_config, seed=42),
    )
    (tmp_path / "case.json").write_text(case.model_dump_json(indent=2))
    return tmp_path


class TestMarkReused:
    """mark_reused() must synthesize completed state when artifacts exist but run_state is missing."""

    def test_mark_reused_existing_completed(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        # Set up a completed stage
        ctx.mark_completed("compare", StageResult(summary="done"), finished_at="2026-01-01T00:00:00Z")
        assert ctx.state.stages["compare"].status == "completed"
        assert ctx.state.stages["compare"].reused is False

        # Reuse it
        ctx.mark_reused("compare")
        assert ctx.state.stages["compare"].status == "completed"
        assert ctx.state.stages["compare"].reused is True

    def test_mark_reused_synthesizes_from_artifact(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        # No stage state exists, but artifact does
        output = ctx.output_path("compare")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("[]")

        ctx.mark_reused("compare")
        stage = ctx.state.stages["compare"]
        assert stage.status == "completed"
        assert stage.reused is True
        assert stage.result is not None
        assert stage.result.primary_output == str(output)
        assert stage.result.metadata == {"synthetic": True}

    def test_mark_reused_synthesizes_without_artifact(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        # No stage state, no artifact
        ctx.mark_reused("compare")
        stage = ctx.state.stages["compare"]
        assert stage.status == "completed"
        assert stage.reused is True
        assert stage.result is not None
        assert stage.result.primary_output is None
        assert stage.result.output_paths == []

    def test_reused_stage_satisfies_prereqs(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        ctx.mark_reused("compare")
        assert ctx.prereqs_satisfied(("compare",)) is True


class TestMarkSkipped:
    """mark_skipped() must never overwrite completed state."""

    def test_skipped_does_not_overwrite_completed(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        ctx.mark_completed("compare", StageResult(summary="done"), finished_at="2026-01-01T00:00:00Z")
        ctx.mark_skipped("compare", reason="outside selected range")
        assert ctx.state.stages["compare"].status == "completed"

    def test_skipped_creates_new_state_if_absent(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        ctx.mark_skipped("compare", reason="explicitly skipped")
        assert ctx.state.stages["compare"].status == "skipped"
        assert ctx.state.stages["compare"].error == "explicitly skipped"

    def test_skipped_overwrites_failed_state(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        ctx.state.stages["compare"] = StageState(name="compare", status="failed", error="boom")
        ctx.mark_skipped("compare", reason="outside selected range")
        assert ctx.state.stages["compare"].status == "skipped"


class TestPrereqsSatisfied:
    def test_missing_stage_fails(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        assert ctx.prereqs_satisfied(("compare",)) is False

    def test_skipped_stage_fails(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        ctx.mark_skipped("compare", reason="test")
        assert ctx.prereqs_satisfied(("compare",)) is False

    def test_completed_stage_passes(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        ctx.mark_completed("compare", StageResult(), finished_at="2026-01-01T00:00:00Z")
        assert ctx.prereqs_satisfied(("compare",)) is True

    def test_empty_requires_always_passes(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        assert ctx.prereqs_satisfied(()) is True


class TestStatePersistence:
    def test_save_and_reload(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        ctx.mark_completed("compare", StageResult(summary="5 findings"), finished_at="2026-01-01T00:00:00Z")
        ctx.save_state()

        ctx2 = RunContext(workspace)
        assert ctx2.state.stages["compare"].status == "completed"
        assert ctx2.state.stages["compare"].result.summary == "5 findings"
