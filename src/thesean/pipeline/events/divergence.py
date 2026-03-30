"""Low-level divergence computation: per-step scoring, persistence checking."""

from __future__ import annotations

from typing import Any

from thesean.pipeline.events.config import EventDetectionConfig


def extract_step_signals(step: dict[str, Any]) -> dict[str, float]:
    """Extract numeric signals from a raw episode step dict.

    Maps F1 world model per-step data to named signals. Unknown keys are
    silently ignored so this works with partial data.
    """
    signals: dict[str, float] = {}

    # Actions: steer, throttle, brake
    action = step.get("action")
    if action is not None and hasattr(action, "__getitem__"):
        if len(action) > 0:
            signals["steering"] = float(action[0])
        if len(action) > 1:
            signals["throttle"] = float(action[1])
        if len(action) > 2:
            signals["brake"] = float(action[2])

    # Car state
    car_state = step.get("car_state", {})
    if isinstance(car_state, dict):
        for key in ("x", "y", "theta", "velocity"):
            if key in car_state:
                signals[key] = float(car_state[key])

    # Track progress
    if "track_progress" in step:
        signals["progress"] = float(step["track_progress"])

    # Reward
    if "reward" in step:
        signals["reward"] = float(step["reward"])

    # Info-based signals
    info = step.get("info", {})
    if isinstance(info, dict) and "offtrack_steps" in info:
        signals["offtrack_risk"] = float(info["offtrack_steps"])

    # Aux (LiDAR)
    aux = step.get("aux")
    if aux is not None and hasattr(aux, "__getitem__") and len(aux) > 1:
        lidar = [float(aux[i]) for i in range(1, min(16, len(aux)))]
        if lidar:
            signals["boundary_margin"] = min(lidar)

    return signals


def compute_step_deltas(
    signals_a: dict[str, float], signals_b: dict[str, float]
) -> dict[str, float]:
    """Compute per-signal absolute deltas between two step signal dicts."""
    deltas: dict[str, float] = {}
    for key in signals_a:
        if key in signals_b:
            deltas[f"{key}_delta"] = abs(signals_a[key] - signals_b[key])
    return deltas


def compute_divergence_score(
    deltas: dict[str, float], config: EventDetectionConfig
) -> float:
    """Weighted sum of active signal deltas."""
    weights = config.signal_weights
    active = set(config.active_signals) if config.active_signals else set(weights.keys())
    score = 0.0
    total_weight = 0.0
    for signal_name, weight in weights.items():
        if signal_name in active and signal_name in deltas:
            score += weight * deltas[signal_name]
            total_weight += weight
    # Normalize by total active weight to keep score scale consistent
    if total_weight > 0:
        score /= total_weight
    return score


def find_persistent_onset(
    scores: list[float], threshold: float, persistence_k: int
) -> int | None:
    """Find first step where score exceeds threshold for k consecutive steps.

    Returns the onset step index, or None if no persistent divergence found.
    """
    run_start: int | None = None
    run_length = 0
    for i, score in enumerate(scores):
        if score > threshold:
            if run_start is None:
                run_start = i
            run_length += 1
            if run_length >= persistence_k:
                return run_start
        else:
            run_start = None
            run_length = 0
    return None
