from __future__ import annotations

from typing import Any


class ProgressMetric:
    """Track progress at episode end (from env.get_progress())."""

    def metric_id(self) -> str:
        return "progress"

    def higher_is_better(self) -> bool:
        return True

    def compute(self, episodes: list[dict[str, Any]]) -> dict[str, Any]:
        per_episode = [ep["final_track_progress"] for ep in episodes]
        return {
            "primary_value": sum(per_episode) / len(per_episode) if per_episode else 0.0,
            "unit": "fraction",
            "per_episode": per_episode,
            "breakdown": {},
        }
