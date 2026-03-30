"""Live step update — transient dataclasses for real-time telemetry during evaluation runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LiveStepUpdate:
    """Immutable snapshot of a single step during live evaluation.

    Transient — never persisted, crosses thread/process boundaries via queues.
    Must be picklable for multiprocessing.Queue.
    """

    run_id: str              # "a" or "b"
    episode_idx: int         # 0-based
    episode_total: int
    step: int                # 0-based within episode
    progress: float          # 0.0-1.0 (track progress)
    reward: float = 0.0
    done: bool = False
    termination: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
    action: list[float] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)
    obs: Any = None
    timestamp: float = 0.0

    # Backward-compat aliases
    @property
    def side(self) -> str:
        return self.run_id

    @property
    def episode(self) -> int:
        return self.episode_idx + 1

    @property
    def track_progress(self) -> float:
        return self.progress

    @property
    def car_state(self) -> dict[str, Any]:
        return self.state


@dataclass(frozen=True)
class LivePairFrame:
    """Pair-aware compare frame — one per lockstep tick."""

    episode_idx: int
    episode_total: int
    tick: int                # lockstep iteration count
    a: LiveStepUpdate | None
    b: LiveStepUpdate | None
    both_done: bool
    max_steps: int = 0
