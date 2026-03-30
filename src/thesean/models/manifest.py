from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from thesean.models.run import Run


class RunManifest(BaseModel):
    run_id: str
    description: str = ""
    world_model_weights: str
    planner_config: dict[str, Any]
    env_config: dict[str, Any]
    num_episodes: int = 20
    seed: int = 42

    def to_run(self) -> Run:
        """Convert to a Run domain model."""
        from thesean.models.run import Run

        return Run.from_manifest(self)
