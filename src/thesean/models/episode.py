"""Episode outcome models for Phase 2 — run-level outcomes and verdict summary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Display name mapping ─────────────────────────────────────────────────────

METRIC_DISPLAY_NAMES: dict[str, str] = {
    "final_track_progress": "completion",
    "off_track_rate": "off-track rate",
    "total_reward": "total reward",
    "fastest_lap_time": "fastest lap",
}


# ── EpisodeRecord ────────────────────────────────────────────────────────────

class EpisodeRecord(BaseModel):
    """Per-episode outcome record from a single run side (a or b).

    Fields map directly to values in runs/{side}/episodes.json.
    """

    model_config = ConfigDict(extra="ignore")

    episode_idx: int
    final_track_progress: float = 0.0
    total_reward: float = 0.0
    termination: str | None = None
    fastest_lap_time: float | None = None
    lap_count: int = 0
    completed: bool = False


# ── EpisodeOutcome ───────────────────────────────────────────────────────────

class EpisodeOutcome(BaseModel):
    """Aggregate outcome for one side (a or b) across all episodes."""

    model_config = ConfigDict(extra="ignore")

    side: str
    episodes: list[EpisodeRecord]
    mean_progress: float
    completion_rate: float
    mean_reward: float
    off_track_rate: float
    fastest_lap: float | None


# ── OutcomeSummary ───────────────────────────────────────────────────────────

class OutcomeSummary(BaseModel):
    """Persisted summary of A vs B comparison outcomes.

    Written to analysis/outcomes.json after run_analysis() completes.
    All display strings are pre-computed so the TUI only loads and renders.
    """

    model_config = ConfigDict(extra="ignore")

    verdict: Literal["regression", "improvement", "no_change", "mixed"]
    primary_metric: str
    primary_metric_display: str
    baseline_value: float
    candidate_value: float
    delta_pct: float
    significant: bool
    regression_count: int
    improvement_count: int
    no_change_count: int
    verdict_headline: str
    primary_metric_line: str
    findings_count_line: str
    top_run: dict[str, str] | None = None  # e.g., {"side": "b", "episode_id": "ep_0002"}
    recommended_run_ids: list[str] = Field(default_factory=list)
    episodes_a: list[EpisodeRecord] = Field(default_factory=list)
    episodes_b: list[EpisodeRecord] = Field(default_factory=list)
