from __future__ import annotations

from typing import Any


class OffTrackRateMetric:
    """Fraction of steps spent off-track."""

    def metric_id(self) -> str:
        return "offtrack_rate"

    def higher_is_better(self) -> bool:
        return False

    def compute(self, episodes: list[dict[str, Any]]) -> dict[str, Any]:
        per_episode = []
        for ep in episodes:
            steps = ep["steps"]
            if not steps:
                per_episode.append(0.0)
                continue
            off = sum(1 for s in steps if not s["info"].get("on_track", True))
            per_episode.append(off / len(steps))

        return {
            "primary_value": sum(per_episode) / len(per_episode) if per_episode else 0.0,
            "unit": "fraction",
            "per_episode": per_episode,
            "breakdown": {},
        }
