from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MetricResult(BaseModel):
    metric_id: str
    value: float
    unit: str | None = None
    higher_is_better: bool
    per_episode: list[float] = []
    breakdown: dict[str, Any] = {}
