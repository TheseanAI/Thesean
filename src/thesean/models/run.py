"""Run model — a single execution configuration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from thesean.models.manifest import RunManifest


class Run(BaseModel):
    """A fully specified run configuration."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str

    # Component references
    world_model_ref: str = ""
    planner_ref: str = ""
    seed: int = 42
    num_episodes: int = Field(default=20, alias="horizon")

    # Full configs (hydrated from refs)
    planner_config: dict[str, Any] = Field(default_factory=dict)
    env_config: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_manifest(cls, manifest: RunManifest) -> Run:
        """Create a Run from a legacy RunManifest."""
        return cls(
            id=manifest.run_id,
            world_model_ref=manifest.world_model_weights,
            planner_config=manifest.planner_config,
            env_config=manifest.env_config,
            seed=manifest.seed,
            num_episodes=manifest.num_episodes,  # type: ignore[call-arg]
        )

    def to_manifest(self) -> RunManifest:
        """Convert back to a RunManifest for pipeline compatibility."""
        return RunManifest(
            run_id=self.id,
            world_model_weights=self.world_model_ref,
            planner_config=self.planner_config,
            env_config=self.env_config,
            num_episodes=self.num_episodes,
            seed=self.seed,
        )
