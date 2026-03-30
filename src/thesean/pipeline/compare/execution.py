"""Execution-only logic: run episodes, compute metrics, save outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesean.core.contracts import AdapterFactory, EnvPlugin, PlannerPlugin, WorldModelPlugin
from thesean.models import MetricResult, RunManifest
from thesean.pipeline.episodes import run_episodes
from thesean.pipeline.metrics_util import compute_and_filter_metrics


def setup_components(
    manifest: RunManifest, factory: AdapterFactory
) -> tuple[EnvPlugin, WorldModelPlugin, PlannerPlugin]:
    """Instantiate env, world model, and planner from a manifest via factory."""
    env = factory.create_env(manifest.env_config)
    wm = factory.create_world_model(manifest.world_model_weights, device="cpu")
    planner = factory.create_planner(dict(manifest.planner_config), wm)
    return env, wm, planner


def save_condition_outputs(
    run_dir: Path,
    episodes: list[dict[str, Any]],
    metrics: list[MetricResult],
) -> None:
    """Save episodes and metrics to a run directory."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "episodes.json").write_text(
        json.dumps(episodes, indent=2, default=str)
    )
    (run_dir / "metrics.json").write_text(
        json.dumps([m.model_dump() for m in metrics], indent=2)
    )


def run_condition(
    manifest: RunManifest,
    run_dir: Path,
    factory: AdapterFactory,
) -> tuple[list[dict[str, Any]], list[MetricResult]]:
    """Run one condition (baseline or candidate): setup, execute, measure, save."""
    env, wm, planner = setup_components(manifest, factory)
    episodes = run_episodes(env, planner, manifest.num_episodes, manifest.seed)
    metrics = compute_and_filter_metrics(episodes, factory, wm, env, manifest.seed)
    save_condition_outputs(run_dir, episodes, metrics)
    return episodes, metrics
