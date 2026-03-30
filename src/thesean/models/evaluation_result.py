"""EvaluationResult -- typed immutable snapshot of a completed evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigSnapshot(BaseModel):
    """Frozen copy of the case definition and adapter info at time of evaluation."""

    model_config = ConfigDict(extra="ignore")

    case_id: str
    track_ref: str = ""
    episode_count: int = 0
    eval_seeds: list[int] | None = None
    run_a_world_model_ref: str = ""
    run_b_world_model_ref: str = ""
    run_a_planner_ref: str = ""
    run_b_planner_ref: str = ""
    adapter_name: str = ""


class EvaluationResult(BaseModel):
    """Immutable snapshot of a completed evaluation.

    Saved to analysis/result.json after run_analysis() completes.
    Bundles episode records, outcome summary, events data, and a
    config snapshot of the case definition at time of evaluation.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())

    # Config snapshot -- frozen copy of case definition at eval time
    config: ConfigSnapshot

    # Episode data per side
    episodes_a: list[dict[str, Any]] = Field(default_factory=list)
    episodes_b: list[dict[str, Any]] = Field(default_factory=list)

    # Outcome summary (the verdict + metrics)
    outcomes: dict[str, Any] = Field(default_factory=dict)

    # Events data (optional -- event extraction can fail)
    events: dict[str, Any] | None = None
