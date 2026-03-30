"""Typed wizard state — pure data models, no I/O."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class WeightInfo(BaseModel):
    name: str
    path: str
    size_mb: float
    mtime: str


class ChangeType(str, Enum):
    WEIGHTS_ONLY = "weights_only"
    PLANNER_ONLY = "planner_only"
    BOTH = "both"
    OTHER = "other"


class InitAnswers(BaseModel):
    adapter_name: str
    repo: Path
    weights: list[WeightInfo]
    baseline_weight: WeightInfo
    candidate_weight: WeightInfo
    change_type: ChangeType
    baseline_planner_config: dict[str, Any]
    candidate_planner_config: dict[str, Any]
    env_id: str
    env_config: dict[str, Any]
    num_episodes: int = 20
    seed: int = 42
