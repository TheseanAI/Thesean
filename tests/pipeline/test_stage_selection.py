"""Tests for stage selection validation and range logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from thesean.models.case import Case
from thesean.models.run import Run
from thesean.pipeline.context import RunContext, StageNameError


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Create a minimal valid workspace."""
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

    case = Case(
        id="test-case",
        run_a=Run(id="baseline", world_model_ref=weights, planner_config=planner, env_config=env_config, seed=42),
        run_b=Run(id="candidate", world_model_ref=weights, planner_config=planner, env_config=env_config, seed=42),
    )
    (tmp_path / "case.json").write_text(case.model_dump_json(indent=2))
    return tmp_path


PIPELINE_NAMES = ("compare", "isolate", "attribute", "report")


class TestBadStageNames:
    def test_bad_from_stage(self, workspace: Path) -> None:
        with pytest.raises(StageNameError, match="Unknown stage 'bogus' in --from"):
            RunContext(workspace, from_stage="bogus", pipeline_names=PIPELINE_NAMES)

    def test_bad_to_stage(self, workspace: Path) -> None:
        with pytest.raises(StageNameError, match="Unknown stage 'nope' in --to"):
            RunContext(workspace, to_stage="nope", pipeline_names=PIPELINE_NAMES)

    def test_bad_skip_stage(self, workspace: Path) -> None:
        with pytest.raises(StageNameError, match="Unknown stage 'fake' in --skip"):
            RunContext(workspace, skip={"fake"}, pipeline_names=PIPELINE_NAMES)

    def test_from_after_to(self, workspace: Path) -> None:
        with pytest.raises(StageNameError, match="--from 'report' comes after --to 'compare'"):
            RunContext(workspace, from_stage="report", to_stage="compare",
                       pipeline_names=PIPELINE_NAMES)


class TestStageSelected:
    def test_no_range_selects_all(self, workspace: Path) -> None:
        ctx = RunContext(workspace)
        names = list(PIPELINE_NAMES)
        for name in names:
            assert ctx.stage_selected(name, names) is True

    def test_from_stage(self, workspace: Path) -> None:
        ctx = RunContext(workspace, from_stage="isolate", pipeline_names=PIPELINE_NAMES)
        names = list(PIPELINE_NAMES)
        assert ctx.stage_selected("compare", names) is False
        assert ctx.stage_selected("isolate", names) is True
        assert ctx.stage_selected("attribute", names) is True
        assert ctx.stage_selected("report", names) is True

    def test_to_stage(self, workspace: Path) -> None:
        ctx = RunContext(workspace, to_stage="isolate", pipeline_names=PIPELINE_NAMES)
        names = list(PIPELINE_NAMES)
        assert ctx.stage_selected("compare", names) is True
        assert ctx.stage_selected("isolate", names) is True
        assert ctx.stage_selected("attribute", names) is False
        assert ctx.stage_selected("report", names) is False

    def test_from_and_to(self, workspace: Path) -> None:
        ctx = RunContext(workspace, from_stage="isolate", to_stage="attribute",
                         pipeline_names=PIPELINE_NAMES)
        names = list(PIPELINE_NAMES)
        assert ctx.stage_selected("compare", names) is False
        assert ctx.stage_selected("isolate", names) is True
        assert ctx.stage_selected("attribute", names) is True
        assert ctx.stage_selected("report", names) is False


class TestValidPipelineNames:
    def test_valid_from(self, workspace: Path) -> None:
        # Should not raise
        ctx = RunContext(workspace, from_stage="isolate", pipeline_names=PIPELINE_NAMES)
        assert ctx.from_stage == "isolate"

    def test_valid_skip(self, workspace: Path) -> None:
        ctx = RunContext(workspace, skip={"isolate", "attribute"}, pipeline_names=PIPELINE_NAMES)
        assert ctx.skip == {"isolate", "attribute"}

    def test_no_validation_without_pipeline_names(self, workspace: Path) -> None:
        # Should not raise even with invalid names when pipeline_names is empty
        ctx = RunContext(workspace, from_stage="bogus")
        assert ctx.from_stage == "bogus"
