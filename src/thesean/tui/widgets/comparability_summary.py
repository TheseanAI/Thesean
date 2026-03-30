"""Comparability summary widget — shows shared config + checkpoint comparison."""

from __future__ import annotations

from typing import Any

from textual.widgets import Static


class ComparabilitySummary(Static):
    """Displays shared config and checkpoint diff for the always-compare builder."""

    DEFAULT_CSS = """
    ComparabilitySummary {
        height: auto;
        padding: 1 2;
        color: $text-muted;
    }
    """

    def update_comparison(
        self,
        track: str,
        episodes: int,
        detail_a: str,
        detail_b: str,
        env_overrides: dict[str, Any] | None = None,
        planner_diff: str | None = None,
    ) -> None:
        lines = []
        lines.append(f"Shared: TRACK={track or '(none)'} | EPISODES={episodes}")

        if env_overrides:
            parts = [f"{k}={v}" for k, v in env_overrides.items()]
            lines.append(f"Env: {', '.join(parts)}")

        if detail_a != detail_b:
            lines.append(f"Checkpoint: baseline={detail_a} vs candidate={detail_b}")
        else:
            lines.append("Checkpoint: (identical -- not a valid comparison)")

        if planner_diff:
            lines.append(f"Planner: {planner_diff}")

        track_ok = bool(track)
        lines.append(f"Checks: track {'OK' if track_ok else 'WARN: no track selected'}")

        self.update("\n".join(lines))
