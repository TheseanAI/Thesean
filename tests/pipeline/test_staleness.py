"""Tests for staleness detection logic."""

from __future__ import annotations

import pytest

from thesean.models.case import Case
from thesean.models.evaluation_result import ConfigSnapshot, EvaluationResult
from thesean.models.run import Run
from thesean.pipeline.staleness import is_result_stale


def _make_case(**kw) -> Case:
    kw.setdefault("id", "c1")
    kw.setdefault("track_ref", "monza")
    kw.setdefault("episode_count", 5)
    kw.setdefault("run_a", Run(id="a", world_model_ref="wm_a.pth"))
    kw.setdefault("run_b", Run(id="b", world_model_ref="wm_b.pth"))
    return Case(**kw)


def _make_result(case: Case) -> EvaluationResult:
    snap = ConfigSnapshot(
        case_id=case.id,
        track_ref=case.track_ref,
        episode_count=case.episode_count,
        eval_seeds=case.eval_seeds,
        run_a_world_model_ref=case.run_a.world_model_ref,
        run_b_world_model_ref=case.run_b.world_model_ref if case.run_b else "",
        run_a_planner_ref=case.run_a.planner_ref,
        run_b_planner_ref=case.run_b.planner_ref if case.run_b else "",
    )
    return EvaluationResult(config=snap)


@pytest.mark.unit
class TestStalenessDetection:

    def test_matching_config_is_not_stale(self) -> None:
        case = _make_case()
        result = _make_result(case)
        assert not is_result_stale(case, result)

    def test_different_track_ref_is_stale(self) -> None:
        case = _make_case(track_ref="monza")
        result = _make_result(case)
        # Now change the case
        case2 = _make_case(track_ref="silverstone")
        assert is_result_stale(case2, result)

    def test_different_episode_count_is_stale(self) -> None:
        case = _make_case(episode_count=5)
        result = _make_result(case)
        case2 = _make_case(episode_count=10)
        assert is_result_stale(case2, result)

    def test_different_world_model_is_stale(self) -> None:
        case = _make_case()
        result = _make_result(case)
        case2 = _make_case(run_a=Run(id="a", world_model_ref="wm_new.pth"))
        assert is_result_stale(case2, result)
