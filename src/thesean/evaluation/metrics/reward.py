from __future__ import annotations

from typing import Any


class CumulativeRewardMetric:
    """Sum of rewards over the episode."""

    def metric_id(self) -> str:
        return "cumulative_reward"

    def higher_is_better(self) -> bool:
        return True

    def compute(self, episodes: list[dict[str, Any]]) -> dict[str, Any]:
        per_episode = [ep["total_reward"] for ep in episodes]
        return {
            "primary_value": sum(per_episode) / len(per_episode) if per_episode else 0.0,
            "unit": "reward",
            "per_episode": per_episode,
            "breakdown": {},
        }
