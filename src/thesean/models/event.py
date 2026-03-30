"""Event model — a detected divergence point between two runs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from thesean.models.signal import SignalValue

EventType = Literal[
    "first_signal_divergence",
    "first_action_divergence",
    "first_risk_spike",
    "first_boundary_collapse",
    "terminal",
    "max_metric_gap",
    # Phase 3 event types
    "first_divergence",
    "divergence_window",
    "risk_spike",
    "off_track_terminal",
    "max_gap",
]


class Event(BaseModel):
    """A detected divergence event at a specific step."""

    id: str
    type: EventType
    step: int
    time_s: float | None = None
    severity: Literal["info", "warning", "critical"] = "warning"
    score: float = 0.0
    persistence_k: int = 1
    active_signals: list[SignalValue] = Field(default_factory=list)
    local_window: tuple[int, int] | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
