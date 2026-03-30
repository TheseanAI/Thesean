"""Explanation model — a tier-aware attribution hypothesis for an event."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from thesean.models.signal import SignalValue


class Explanation(BaseModel):
    """An evidence-backed explanation for a detected event."""

    id: str
    event_id: str
    label: str
    confidence: float = 0.0
    tier: Literal["tier_0", "tier_1", "tier_2", "tier_3"] = "tier_0"
    support_basis: list[str] = Field(default_factory=list)
    competing: list[str] = Field(default_factory=list)
    supporting_signals: list[SignalValue] = Field(default_factory=list)
    falsifiers: list[str] = Field(default_factory=list)
