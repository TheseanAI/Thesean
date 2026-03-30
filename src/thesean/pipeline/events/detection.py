"""High-level event detection: produce Event list from paired episode data."""

from __future__ import annotations

import uuid
from typing import Any

from thesean.models.event import Event
from thesean.models.signal import SignalValue
from thesean.pipeline.events.config import EventDetectionConfig
from thesean.pipeline.events.divergence import (
    compute_divergence_score,
    compute_step_deltas,
    extract_step_signals,
    find_persistent_onset,
)


def _make_id() -> str:
    return f"evt-{uuid.uuid4().hex[:8]}"


def _align_episodes(
    baseline_episodes: list[dict[str, Any]],
    candidate_episodes: list[dict[str, Any]],
) -> list[tuple[list[dict[str, Any]], list[dict[str, Any]]]]:
    """Pair episodes by index. Returns list of (baseline_steps, candidate_steps)."""
    n = min(len(baseline_episodes), len(candidate_episodes))
    pairs = []
    for i in range(n):
        b_steps = baseline_episodes[i].get("steps", [])
        c_steps = candidate_episodes[i].get("steps", [])
        if b_steps and c_steps:
            pairs.append((b_steps, c_steps))
    return pairs


def _aggregate_step_pairs(
    episode_pairs: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]],
) -> tuple[list[dict[str, float]], list[dict[str, float]], int]:
    """Average signals across episodes at each step.

    Returns (avg_signals_a, avg_signals_b, max_steps).
    """
    if not episode_pairs:
        return [], [], 0

    max_steps = max(
        min(len(b), len(c)) for b, c in episode_pairs
    )

    avg_a: list[dict[str, float]] = []
    avg_b: list[dict[str, float]] = []

    for t in range(max_steps):
        sums_a: dict[str, float] = {}
        sums_b: dict[str, float] = {}
        counts_a: dict[str, int] = {}
        counts_b: dict[str, int] = {}
        for b_steps, c_steps in episode_pairs:
            if t < len(b_steps):
                for k, v in extract_step_signals(b_steps[t]).items():
                    sums_a[k] = sums_a.get(k, 0.0) + v
                    counts_a[k] = counts_a.get(k, 0) + 1
            if t < len(c_steps):
                for k, v in extract_step_signals(c_steps[t]).items():
                    sums_b[k] = sums_b.get(k, 0.0) + v
                    counts_b[k] = counts_b.get(k, 0) + 1
        avg_a.append({k: sums_a[k] / counts_a[k] for k in sums_a})
        avg_b.append({k: sums_b[k] / counts_b[k] for k in sums_b})

    return avg_a, avg_b, max_steps


def detect_events(
    baseline_episodes: list[dict[str, Any]],
    candidate_episodes: list[dict[str, Any]],
    config: EventDetectionConfig | None = None,
) -> list[Event]:
    """Detect divergence events between baseline and candidate episode sets.

    Implements 6 event classes:
    1. First signal divergence (weighted score > threshold for k steps)
    2. First planner action divergence (action magnitude delta)
    3. First risk spike (offtrack risk delta)
    4. First boundary-margin collapse
    5. Terminal event (done=True with termination reason)
    6. Max metric gap (largest instantaneous divergence)
    """
    if config is None:
        config = EventDetectionConfig()

    episode_pairs = _align_episodes(baseline_episodes, candidate_episodes)
    if not episode_pairs:
        return []

    avg_a, avg_b, max_steps = _aggregate_step_pairs(episode_pairs)
    if max_steps == 0:
        return []

    limit = config.max_steps if config.max_steps else max_steps

    # Compute per-step deltas and divergence scores
    all_deltas: list[dict[str, float]] = []
    all_scores: list[float] = []
    for t in range(min(limit, max_steps)):
        deltas = compute_step_deltas(avg_a[t], avg_b[t])
        score = compute_divergence_score(deltas, config)
        all_deltas.append(deltas)
        all_scores.append(score)

    events: list[Event] = []

    # 1. First signal divergence
    onset = find_persistent_onset(all_scores, config.threshold, config.persistence_k)
    if onset is not None:
        top_signals = sorted(
            all_deltas[onset].items(), key=lambda x: x[1], reverse=True
        )[:5]
        events.append(Event(
            id=_make_id(),
            type="first_signal_divergence",
            step=onset,
            severity="critical",
            score=all_scores[onset],
            persistence_k=config.persistence_k,
            active_signals=[
                SignalValue(name=k, value=v) for k, v in top_signals
            ],
            local_window=(max(0, onset - 5), min(len(all_scores) - 1, onset + config.persistence_k + 5)),
        ))

    # 2. First action divergence
    for t in range(min(limit, max_steps)):
        action_delta = 0.0
        for key in ("steering_delta", "throttle_delta", "brake_delta"):
            action_delta += all_deltas[t].get(key, 0.0)
        if action_delta > config.action_threshold:
            events.append(Event(
                id=_make_id(),
                type="first_action_divergence",
                step=t,
                severity="warning",
                score=action_delta,
                active_signals=[
                    SignalValue(name=k, value=v)
                    for k, v in all_deltas[t].items()
                    if k in ("steering_delta", "throttle_delta", "brake_delta")
                ],
            ))
            break

    # 3. First risk spike
    for t in range(min(limit, max_steps)):
        risk_a = avg_a[t].get("offtrack_risk", 0.0)
        risk_b = avg_b[t].get("offtrack_risk", 0.0)
        risk_delta = abs(risk_b - risk_a)
        if risk_delta > config.risk_threshold:
            events.append(Event(
                id=_make_id(),
                type="first_risk_spike",
                step=t,
                severity="critical",
                score=risk_delta,
                active_signals=[
                    SignalValue(name="offtrack_risk_a", value=risk_a),
                    SignalValue(name="offtrack_risk_b", value=risk_b),
                ],
            ))
            break

    # 4. First boundary-margin collapse
    for t in range(min(limit, max_steps)):
        margin_a = avg_a[t].get("boundary_margin", 1.0)
        margin_b = avg_b[t].get("boundary_margin", 1.0)
        # Collapse = candidate margin drops below threshold while baseline is safe
        if margin_b < config.boundary_threshold and margin_a > config.boundary_threshold:
            events.append(Event(
                id=_make_id(),
                type="first_boundary_collapse",
                step=t,
                severity="critical",
                score=margin_a - margin_b,
                active_signals=[
                    SignalValue(name="boundary_margin_a", value=margin_a),
                    SignalValue(name="boundary_margin_b", value=margin_b),
                ],
            ))
            break

    # 5. Terminal events — scan individual episodes for done=True
    for ep_idx, (b_steps, c_steps) in enumerate(episode_pairs):
        for t, step in enumerate(c_steps):
            if step.get("done", False) and t < len(b_steps) and not b_steps[t].get("done", False):
                info = step.get("info", {})
                reason = info.get("termination", "unknown") if isinstance(info, dict) else "unknown"
                events.append(Event(
                    id=_make_id(),
                    type="terminal",
                    step=t,
                    severity="critical",
                    score=1.0,
                    metadata={"episode": ep_idx, "reason": reason},
                ))
                break  # One terminal per episode pair
        # Only report first terminal across episodes
        if events and events[-1].type == "terminal":
            break

    # 6. Max metric gap
    if all_scores:
        max_t = max(range(len(all_scores)), key=lambda i: all_scores[i])
        max_score = all_scores[max_t]
        if max_score > 0:
            top_signals = sorted(
                all_deltas[max_t].items(), key=lambda x: x[1], reverse=True
            )[:5]
            events.append(Event(
                id=_make_id(),
                type="max_metric_gap",
                step=max_t,
                severity="info" if max_score < config.threshold else "warning",
                score=max_score,
                active_signals=[
                    SignalValue(name=k, value=v) for k, v in top_signals
                ],
            ))

    # Sort events by step
    events.sort(key=lambda e: e.step)
    return events
