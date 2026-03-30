"""Configuration for event detection."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventDetectionConfig(BaseModel):
    """Tunable parameters for divergence detection."""

    # Weighted divergence score threshold for declaring an event
    threshold: float = 0.15

    # Number of consecutive steps above threshold to confirm persistence
    persistence_k: int = 4

    # Per-signal weights for composite divergence score
    signal_weights: dict[str, float] = Field(default_factory=lambda: {
        "steering_delta": 0.25,
        "throttle_delta": 0.15,
        "brake_delta": 0.10,
        "heading_delta": 0.20,
        "speed_delta": 0.10,
        "progress_delta": 0.10,
        "reward_delta": 0.10,
    })

    # Which signals are active (subset of signal_weights keys)
    active_signals: list[str] | None = None

    # Action divergence threshold (L1 norm of action delta)
    action_threshold: float = 0.3

    # Risk spike threshold (absolute offtrack risk delta)
    risk_threshold: float = 3.0

    # Boundary margin collapse: min LiDAR distance threshold
    boundary_threshold: float = 0.15

    # Max steps to scan (None = all)
    max_steps: int | None = None
