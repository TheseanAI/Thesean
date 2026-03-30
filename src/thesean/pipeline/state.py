"""Stage execution state models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

StageStatus = Literal["pending", "running", "completed", "failed", "skipped"]


class StageResult(BaseModel):
    primary_output: str | None = None
    output_paths: list[str] = Field(default_factory=list)
    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StageState(BaseModel):
    name: str
    status: StageStatus = "pending"
    result: StageResult | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    reused: bool = False


class RunState(BaseModel):
    stages: dict[str, StageState] = Field(default_factory=dict)
