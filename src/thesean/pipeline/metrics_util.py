"""Shared metric computation logic used by both compare and isolation pipelines."""

from __future__ import annotations

import math
from typing import Any

from thesean.core.contracts import AdapterFactory
from thesean.models import MetricResult


def compute_and_filter_metrics(
    episodes: list[dict[str, Any]],
    factory: AdapterFactory,
    world_model: Any = None,
    env: Any = None,
    seed: int = 42,
    skip_metrics: set[str] | None = None,
) -> list[MetricResult]:
    """Compute all metrics on episodes, filtering NaN values and optionally skipping metrics.

    Args:
        episodes: Episode data dicts.
        factory: Adapter factory providing metric plugins.
        world_model: Optional world model for prediction_error metric.
        env: Optional env for prediction_error metric.
        seed: Random seed.
        skip_metrics: Set of metric IDs to skip (e.g. {"prediction_error"}).

    Returns:
        List of MetricResult with NaN values excluded.
    """
    skip = skip_metrics or set()

    # Inject world_model/env for prediction_error metric
    if world_model is not None and env is not None:
        for ep in episodes:
            ep["_world_model"] = world_model
            ep["_env"] = env
            ep["_seed"] = seed

    results = []
    for metric in factory.get_metrics():
        if metric.metric_id() in skip:
            continue
        raw = metric.compute(episodes)
        val = raw["primary_value"]
        if math.isnan(val):
            continue
        results.append(MetricResult(
            metric_id=metric.metric_id(),
            value=val,
            unit=raw.get("unit"),
            higher_is_better=metric.higher_is_better(),
            per_episode=raw.get("per_episode", []),
            breakdown=raw.get("breakdown", {}),
        ))

    # Clean up injected refs
    for ep in episodes:
        ep.pop("_world_model", None)
        ep.pop("_env", None)
        ep.pop("_seed", None)

    return results
