from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .metric import MetricResult


class SwapFactors(BaseModel):
    world_model: Literal["baseline", "candidate"]
    planner: Literal["baseline", "candidate"]
    env: Literal["baseline", "candidate"]


class SwapTestSpec(BaseModel):
    test_id: str
    factors: SwapFactors


class SwapTestResult(BaseModel):
    test_id: str
    status: Literal["ok", "failed", "skipped"]
    metrics: list[MetricResult] = []
    error: str | None = None
