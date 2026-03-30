"""Standalone comparison logic — pure function, no I/O coupling.

Extracts metric comparison from services.py run_analysis() into a reusable
pure function that accepts typed EpisodeOutcome objects and returns raw
metric data (CompareResult). Display string generation stays in services.py.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from thesean.models.episode import METRIC_DISPLAY_NAMES, EpisodeOutcome, EpisodeRecord

# ── Models ──────────────────────────────────────────────────────────────────


class MetricResult(BaseModel):
    """Per-metric comparison result with raw numeric data."""

    metric_id: str
    baseline_value: float
    candidate_value: float
    higher_is_better: bool
    threshold: float
    delta: float
    delta_badness: float
    significant: bool
    status: Literal["regression", "improvement", "no_change"]


class CompareResult(BaseModel):
    """Typed return for pure comparison data — no display strings.

    Carries all raw metric data needed by services.py to build display strings
    and by report renderers to produce output. Intentionally omits
    verdict_headline, primary_metric_line, findings_count_line (those are
    presentation concerns).
    """

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
    metrics: list[MetricResult]
    top_run: dict[str, str] | None = None
    recommended_run_ids: list[str] = Field(default_factory=list)


# ── Public functions ────────────────────────────────────────────────────────


def build_episode_outcome(side: str, raw_episodes: list[dict]) -> EpisodeOutcome:
    """Convert raw episode dicts to a typed EpisodeOutcome with aggregated metrics.

    Extracted from services.py _build_outcome inner function.
    """
    records: list[EpisodeRecord] = []
    for ep in raw_episodes:
        termination = ep.get("termination", None)
        completed = termination is None or termination == "lap_complete"
        records.append(
            EpisodeRecord(
                episode_idx=ep.get("episode_idx", 0),
                final_track_progress=float(ep.get("final_track_progress", 0.0)),
                total_reward=float(ep.get("total_reward", 0.0)),
                termination=termination,
                fastest_lap_time=ep.get("fastest_lap_time", None),
                lap_count=int(ep.get("lap_count", 0)),
                completed=completed,
            )
        )
    n = len(records) or 1
    mean_progress = sum(r.final_track_progress for r in records) / n
    completion_rate = sum(1 for r in records if r.completed) / n
    mean_reward = sum(r.total_reward for r in records) / n
    off_track_rate = sum(1 for r in records if r.termination == "off_track") / n
    lap_times = [r.fastest_lap_time for r in records if r.fastest_lap_time is not None]
    fastest_lap: float | None = min(lap_times) if lap_times else None
    return EpisodeOutcome(
        side=side,
        episodes=records,
        mean_progress=mean_progress,
        completion_rate=completion_rate,
        mean_reward=mean_reward,
        off_track_rate=off_track_rate,
        fastest_lap=fastest_lap,
    )


def _compute_metric(
    metric_id: str,
    baseline_value: float,
    candidate_value: float,
    higher_is_better: bool,
    threshold: float,
) -> MetricResult:
    """Compute a single metric comparison."""
    delta = candidate_value - baseline_value
    delta_badness = -delta if higher_is_better else delta
    if baseline_value != 0:
        significant = abs(delta_badness / baseline_value) >= threshold
    else:
        significant = False

    if significant and delta_badness > 0:
        status: Literal["regression", "improvement", "no_change"] = "regression"
    elif significant and delta_badness < 0:
        status = "improvement"
    else:
        status = "no_change"

    return MetricResult(
        metric_id=metric_id,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        higher_is_better=higher_is_better,
        threshold=threshold,
        delta=delta,
        delta_badness=delta_badness,
        significant=significant,
        status=status,
    )


def compare_results(
    outcome_a: EpisodeOutcome,
    outcome_b: EpisodeOutcome,
    raw_a: list[dict],
    raw_b: list[dict],
) -> CompareResult:
    """Compare two episode outcomes and return raw metric data.

    Accepts typed EpisodeOutcome objects for metric data (per D-02/COMP-02).
    Also takes raw_a/raw_b for top_run computation (indexes into raw episode
    dicts for reward deltas).

    Returns CompareResult with all raw metric data, NO display strings.
    """
    # Per-metric comparisons
    metrics: list[MetricResult] = []

    metrics.append(
        _compute_metric(
            "final_track_progress",
            outcome_a.mean_progress,
            outcome_b.mean_progress,
            higher_is_better=True,
            threshold=0.10,
        )
    )
    metrics.append(
        _compute_metric(
            "off_track_rate",
            outcome_a.off_track_rate,
            outcome_b.off_track_rate,
            higher_is_better=False,
            threshold=0.10,
        )
    )
    metrics.append(
        _compute_metric(
            "total_reward",
            outcome_a.mean_reward,
            outcome_b.mean_reward,
            higher_is_better=True,
            threshold=0.10,
        )
    )
    # fastest_lap_time only if both sides have data
    if outcome_a.fastest_lap is not None and outcome_b.fastest_lap is not None:
        metrics.append(
            _compute_metric(
                "fastest_lap_time",
                outcome_a.fastest_lap,
                outcome_b.fastest_lap,
                higher_is_better=False,
                threshold=0.05,
            )
        )

    # Determine primary metric and verdict
    significant_metrics = sorted(
        [m for m in metrics if m.significant],
        key=lambda m: m.delta_badness,
        reverse=True,
    )
    if significant_metrics:
        primary = significant_metrics[0]
    else:
        primary = max(metrics, key=lambda m: m.delta_badness)

    regression_count = sum(1 for m in metrics if m.status == "regression" and m.significant)
    improvement_count = sum(1 for m in metrics if m.status == "improvement" and m.significant)
    no_change_count = sum(1 for m in metrics if m.status == "no_change")

    if regression_count > 0 and improvement_count > 0:
        verdict: Literal["regression", "improvement", "no_change", "mixed"] = "mixed"
    elif regression_count > 0:
        verdict = "regression"
    elif improvement_count > 0:
        verdict = "improvement"
    else:
        verdict = "no_change"

    # delta_pct for primary metric
    if primary.baseline_value != 0:
        delta_pct = ((primary.candidate_value - primary.baseline_value) / primary.baseline_value) * 100
    else:
        delta_pct = 0.0

    # top_run: episode with largest |total_reward_a - total_reward_b|
    top_run_info: dict[str, str] | None = None
    recommended: list[str] = []
    n_eps = min(len(raw_a), len(raw_b))
    if n_eps > 0:
        max_delta = -1.0
        best_idx = 0
        deltas_list: list[tuple[float, int]] = []
        for i in range(n_eps):
            reward_a = float(raw_a[i].get("total_reward", 0.0))
            reward_b = float(raw_b[i].get("total_reward", 0.0))
            d = abs(reward_a - reward_b)
            deltas_list.append((d, i))
            if d > max_delta:
                max_delta = d
                best_idx = i
        ep_id = f"ep_{best_idx:04d}"
        top_run_info = {"side": "b", "episode_id": ep_id}
        deltas_list.sort(reverse=True)
        recommended = [f"ep_{idx:04d}" for _, idx in deltas_list[:3]]

    primary_display = METRIC_DISPLAY_NAMES.get(
        primary.metric_id, primary.metric_id.replace("_", " ")
    )

    return CompareResult(
        verdict=verdict,
        primary_metric=primary.metric_id,
        primary_metric_display=primary_display,
        baseline_value=primary.baseline_value,
        candidate_value=primary.candidate_value,
        delta_pct=delta_pct,
        significant=primary.significant,
        regression_count=regression_count,
        improvement_count=improvement_count,
        no_change_count=no_change_count,
        metrics=metrics,
        top_run=top_run_info,
        recommended_run_ids=recommended,
    )
