"""Staleness detection -- compare case definition against evaluation result config."""

from __future__ import annotations

from thesean.models.case import Case
from thesean.models.evaluation_result import EvaluationResult


def is_result_stale(case: Case, result: EvaluationResult) -> bool:
    """Return True if case definition has diverged from the result's config snapshot.

    Compares the comparison-relevant fields: track, episodes, seeds,
    and per-side world model / planner refs.
    """
    cfg = result.config

    if case.track_ref != cfg.track_ref:
        return True
    if case.episode_count != cfg.episode_count:
        return True
    if case.eval_seeds != cfg.eval_seeds:
        return True
    if case.run_a.world_model_ref != cfg.run_a_world_model_ref:
        return True
    if case.run_a.planner_ref != cfg.run_a_planner_ref:
        return True
    if case.run_b is not None:
        if case.run_b.world_model_ref != cfg.run_b_world_model_ref:
            return True
        if case.run_b.planner_ref != cfg.run_b_planner_ref:
            return True

    return False
