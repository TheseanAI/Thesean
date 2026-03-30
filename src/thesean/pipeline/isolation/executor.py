"""Execute a single swap test."""

from __future__ import annotations

import traceback

from thesean.core.contracts import AdapterFactory
from thesean.models import RunManifest, SwapTestResult, SwapTestSpec
from thesean.pipeline.episodes import run_episodes
from thesean.pipeline.metrics_util import compute_and_filter_metrics


def execute_swap_test(
    spec: SwapTestSpec,
    baseline: RunManifest,
    candidate: RunManifest,
    factory: AdapterFactory,
) -> SwapTestResult:
    """Run one swap test combination and compute metrics."""
    try:
        factors = spec.factors

        # Select configs based on factors
        wm_weights = (
            candidate.world_model_weights
            if factors.world_model == "candidate"
            else baseline.world_model_weights
        )
        planner_config = dict(
            candidate.planner_config
            if factors.planner == "candidate"
            else baseline.planner_config
        )
        env_config = (
            candidate.env_config
            if factors.env == "candidate"
            else baseline.env_config
        )

        # Instantiate components via factory
        env = factory.create_env(env_config)
        wm = factory.create_world_model(wm_weights, device="cpu")
        planner = factory.create_planner(planner_config, wm)

        # Use baseline seed and episode count
        episodes = run_episodes(env, planner, baseline.num_episodes, baseline.seed)

        # Compute metrics (skip prediction_error for swap tests — too slow)
        metrics = compute_and_filter_metrics(
            episodes, factory, skip_metrics={"prediction_error"}
        )

        return SwapTestResult(test_id=spec.test_id, status="ok", metrics=metrics)

    except Exception as e:
        return SwapTestResult(
            test_id=spec.test_id,
            status="failed",
            error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
        )
