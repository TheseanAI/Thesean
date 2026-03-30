"""Case model — a complete comparison investigation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from thesean.models.event import Event
from thesean.models.explanation import Explanation
from thesean.models.run import Run


class Case(BaseModel):
    """A fully specified comparison case between two runs."""

    model_config = ConfigDict(extra="ignore")

    id: str
    schema_version: int = 1
    project_id: str = ""
    track_ref: str = ""
    episode_count: int = 5
    eval_seeds: list[int] | None = None
    alignment_method: str = "progress"
    shared_env_overrides: dict[str, Any] = Field(default_factory=dict)
    run_a: Run
    run_b: Run | None = None
    events: list[Event] = Field(default_factory=list)
    explanations: list[Explanation] = Field(default_factory=list)
