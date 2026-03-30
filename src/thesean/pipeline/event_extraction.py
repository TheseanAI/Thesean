"""Event extraction — detect divergence windows, risk spikes, and terminal events from paired episodes."""

from __future__ import annotations

from typing import Any, Literal

from thesean.models.event import Event
from thesean.models.signal import SignalValue

# Divergence thresholds for core signals
_CORE_THRESHOLDS: dict[str, float] = {
    "steering": 0.15,
    "throttle": 0.15,
    "brake": 0.15,
    "speed": 0.2,
}

# Minimum consecutive diverging steps to seed a window
_PERSISTENCE_K = 3

# Gaps shorter than this get absorbed into the surrounding window
_MERGE_GAP = 10

# Windows shorter than this (after merging) are dropped as noise
_MIN_WINDOW_LEN = 5

# Minimum steps between risk spike events to avoid clustering
_RISK_COOLDOWN = 10

# Offtrack risk threshold
_RISK_THRESHOLD = 5


def extract_events_for_episode(
    steps_a: list[dict],
    steps_b: list[dict],
    episode_id: str,
    translator: Any = None,
) -> list[Event]:
    """Extract events from paired A/B episode step data.

    Detects:
    - divergence_window: contiguous spans where core signals differ beyond threshold
    - risk_spike: steps where offtrack_risk exceeds threshold (with cooldown)
    - off_track_terminal: episode ended due to off-track

    Returns events sorted by step ascending.
    """
    if not steps_a or not steps_b:
        return []

    if translator is None:
        raise ValueError("translator is required — pass a SignalTranslator instance")

    min_len = min(len(steps_a), len(steps_b))
    events: list[Event] = []

    # Pre-translate all steps
    prev_vel_a: float | None = None
    prev_vel_b: float | None = None
    translated_a: list[dict[str, float]] = []
    translated_b: list[dict[str, float]] = []

    for i in range(min_len):
        sa = translator.translate_step(steps_a[i], prev_velocity=prev_vel_a)
        sb = translator.translate_step(steps_b[i], prev_velocity=prev_vel_b)
        translated_a.append(sa)
        translated_b.append(sb)
        prev_vel_a = sa["speed"]
        prev_vel_b = sb["speed"]

    # ── 1. Divergence windows ────────────────────────────────────────────
    # Find contiguous spans where any core signal exceeds its threshold
    # for at least _PERSISTENCE_K consecutive steps.
    _extract_divergence_windows(translated_a, translated_b, min_len, episode_id, events)

    # ── 2. Risk spikes ───────────────────────────────────────────────────
    _extract_risk_spikes(translated_a, translated_b, min_len, episode_id, events)

    # ── 3. Off-track terminal ────────────────────────────────────────────
    _extract_terminal(steps_a, steps_b, episode_id, events)

    events.sort(key=lambda e: e.step)
    return events


def _extract_divergence_windows(
    translated_a: list[dict[str, float]],
    translated_b: list[dict[str, float]],
    min_len: int,
    episode_id: str,
    events: list[Event],
) -> None:
    """Detect divergence windows — contiguous spans where core signals differ.

    Uses a two-pass approach:
    1. Find raw diverging spans (>= _PERSISTENCE_K consecutive diverging steps)
    2. Merge spans separated by gaps < _MERGE_GAP into single windows
    """
    if min_len < _PERSISTENCE_K:
        return

    # Build per-step divergence data
    diverging: list[dict[str, float]] = []
    for i in range(min_len):
        exceeded = {}
        for key, threshold in _CORE_THRESHOLDS.items():
            delta = abs(translated_a[i][key] - translated_b[i][key])
            if delta > threshold:
                exceeded[key] = delta
        diverging.append(exceeded)

    # Pass 1: find raw spans of consecutive diverging steps
    raw_spans: list[tuple[int, int]] = []
    span_start: int | None = None
    run_length = 0

    for i in range(min_len):
        if diverging[i]:
            if span_start is None:
                span_start = i
            run_length += 1
        else:
            if span_start is not None and run_length >= _PERSISTENCE_K:
                raw_spans.append((span_start, span_start + run_length - 1))
            span_start = None
            run_length = 0

    if span_start is not None and run_length >= _PERSISTENCE_K:
        raw_spans.append((span_start, span_start + run_length - 1))

    if not raw_spans:
        return

    # Pass 2: merge spans separated by gaps < _MERGE_GAP
    merged: list[tuple[int, int]] = [raw_spans[0]]
    for start, end in raw_spans[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= _MERGE_GAP:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))

    # Emit events for windows that meet minimum length
    window_idx = 0
    for start, end in merged:
        if (end - start + 1) >= _MIN_WINDOW_LEN:
            _emit_divergence_window(
                translated_a, translated_b, diverging,
                start, end, episode_id, window_idx, events,
            )
            window_idx += 1


def _emit_divergence_window(
    translated_a: list[dict[str, float]],
    translated_b: list[dict[str, float]],
    diverging: list[dict[str, float]],
    start: int,
    end: int,
    episode_id: str,
    window_idx: int,
    events: list[Event],
) -> None:
    """Create a divergence_window event for a confirmed span."""
    # Collect all signals that exceeded threshold anywhere in this window
    signal_peaks: dict[str, float] = {}
    for i in range(start, end + 1):
        for key, delta in diverging[i].items():
            if key not in signal_peaks or delta > signal_peaks[key]:
                signal_peaks[key] = delta

    active = [SignalValue(name=k, value=v) for k, v in sorted(signal_peaks.items(), key=lambda x: -x[1])]
    peak_delta = max(signal_peaks.values()) if signal_peaks else 0.0
    duration = end - start + 1

    # Severity based on duration and peak delta
    severity: Literal["info", "warning", "critical"]
    if duration > 20 or peak_delta > 0.5:
        severity = "critical"
    elif duration > 8 or peak_delta > 0.3:
        severity = "warning"
    else:
        severity = "info"

    is_first = window_idx == 0
    events.append(Event(
        id=f"{episode_id}_divergence_{window_idx}_{start}",
        type="first_divergence" if is_first else "divergence_window",
        step=start,
        severity=severity,
        score=peak_delta,
        persistence_k=duration,
        active_signals=active,
        local_window=(start, end),
        metadata={"window_idx": window_idx, "duration": duration},
    ))


def _extract_risk_spikes(
    translated_a: list[dict[str, float]],
    translated_b: list[dict[str, float]],
    min_len: int,
    episode_id: str,
    events: list[Event],
) -> None:
    """Detect all risk spikes with cooldown between them."""
    last_spike_step = -_RISK_COOLDOWN - 1
    spike_idx = 0

    for i in range(min_len):
        ot_a = translated_a[i]["offtrack_risk"]
        ot_b = translated_b[i]["offtrack_risk"]
        worst = max(ot_a, ot_b)

        if worst >= _RISK_THRESHOLD and (i - last_spike_step) > _RISK_COOLDOWN:
            sev: Literal["info", "warning", "critical"] = "critical" if worst >= 8 else "warning"
            events.append(Event(
                id=f"{episode_id}_risk_spike_{spike_idx}_{i}",
                type="risk_spike",
                step=i,
                severity=sev,
                score=worst / 10.0,
                active_signals=[SignalValue(name="offtrack_risk", value=worst)],
            ))
            last_spike_step = i
            spike_idx += 1


def _extract_terminal(
    steps_a: list[dict],
    steps_b: list[dict],
    episode_id: str,
    events: list[Event],
) -> None:
    """Detect off-track terminal events."""
    terminal_step: int | None = None
    for side_steps in (steps_a, steps_b):
        last = side_steps[-1] if side_steps else None
        if last is not None:
            info = last.get("info", {})
            if isinstance(info, dict) and info.get("termination") == "off_track":
                step_idx = len(side_steps) - 1
                if terminal_step is None or step_idx < terminal_step:
                    terminal_step = step_idx

    if terminal_step is not None:
        events.append(Event(
            id=f"{episode_id}_off_track_terminal_{terminal_step}",
            type="off_track_terminal",
            step=terminal_step,
            severity="critical",
            score=1.0,
        ))
