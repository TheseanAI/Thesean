from __future__ import annotations

from typing import Any


class SurvivalStepsMetric:
    """Number of steps before episode termination."""

    def metric_id(self) -> str:
        return "survival_steps"

    def higher_is_better(self) -> bool:
        return True

    def compute(self, episodes: list[dict[str, Any]]) -> dict[str, Any]:
        per_episode = [float(ep["total_steps"]) for ep in episodes]
        return {
            "primary_value": sum(per_episode) / len(per_episode) if per_episode else 0.0,
            "unit": "steps",
            "per_episode": per_episode,
            "breakdown": {},
        }
