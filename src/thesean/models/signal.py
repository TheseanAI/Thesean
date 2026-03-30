"""Signal value model for event detection and display."""

from __future__ import annotations

from pydantic import BaseModel


class SignalValue(BaseModel):
    """A single named signal measurement at a point in time."""

    name: str
    value: float
    unit: str | None = None
    display_format: str = ".3f"
