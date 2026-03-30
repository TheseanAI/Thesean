from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ComparisonStatus = Literal["regression", "improvement", "no_change"]


class MetricComparison(BaseModel):
    metric_id: str
    baseline_value: float
    candidate_value: float
    delta: float
    delta_badness: float
    higher_is_better: bool
    baseline_per_episode: list[float] = Field(default_factory=list)
    candidate_per_episode: list[float] = Field(default_factory=list)
    ci_low: float | None = None
    ci_high: float | None = None
    p_value: float | None = None
    p_value_adj: float | None = None
    significant: bool = False
    status: ComparisonStatus


class ComparisonReport(BaseModel):
    baseline_run_dir: str
    candidate_run_dir: str
    metrics: list[MetricComparison]
