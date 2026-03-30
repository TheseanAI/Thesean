"""Project model — represents a discovered adapter-backed repo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DiscoveredAssets(BaseModel):
    """Assets discovered by adapter's detect_project."""

    weights: list[dict[str, Any]] = Field(default_factory=list)
    envs: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    configs: list[str] = Field(default_factory=list)


class Project(BaseModel):
    """A Thesean project rooted at a repo with a bound adapter."""

    project_root: Path
    adapter_name: str
    discovered_assets: DiscoveredAssets = Field(default_factory=DiscoveredAssets)
