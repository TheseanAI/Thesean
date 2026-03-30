"""Shared widget test helpers."""

from __future__ import annotations

from thesean.models.event import Event


def make_events(n: int = 3) -> list[Event]:
    return [
        Event(
            id=f"evt-{i}",
            type="first_divergence",
            step=i * 10,
            severity="warning" if i % 2 == 0 else "info",
        )
        for i in range(n)
    ]
