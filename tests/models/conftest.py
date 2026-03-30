"""Shared model builders for tests/models/."""

from __future__ import annotations

from typing import Any

from thesean.models.comparison import MetricComparison
from thesean.models.episode import EpisodeRecord, OutcomeSummary
from thesean.models.event import Event


def make_event(
    step: int = 0,
    type: str = "first_divergence",
    severity: str = "warning",
    **kw: Any,
) -> Event:
    kw.setdefault("id", f"evt-{step}")
    return Event(step=step, type=type, severity=severity, **kw)


def make_episode_record(idx: int = 0, **kw: Any) -> EpisodeRecord:
    kw.setdefault("episode_idx", idx)
    return EpisodeRecord(**kw)


def make_metric_comparison(metric_id: str = "track_progress", **kw: Any) -> MetricComparison:
    kw.setdefault("baseline_value", 0.8)
    kw.setdefault("candidate_value", 0.7)
    kw.setdefault("delta", kw["candidate_value"] - kw["baseline_value"])
    kw.setdefault("delta_badness", abs(kw["delta"]))
    kw.setdefault("higher_is_better", True)
    kw.setdefault("status", "regression")
    return MetricComparison(metric_id=metric_id, **kw)


def make_outcome_summary(**kw: Any) -> OutcomeSummary:
    kw.setdefault("verdict", "regression")
    kw.setdefault("primary_metric", "final_track_progress")
    kw.setdefault("primary_metric_display", "completion")
    kw.setdefault("baseline_value", 0.8)
    kw.setdefault("candidate_value", 0.6)
    kw.setdefault("delta_pct", -25.0)
    kw.setdefault("significant", True)
    kw.setdefault("regression_count", 1)
    kw.setdefault("improvement_count", 0)
    kw.setdefault("no_change_count", 0)
    kw.setdefault("verdict_headline", "Regression detected")
    kw.setdefault("primary_metric_line", "completion: 0.80 → 0.60 (−25.0%)")
    kw.setdefault("findings_count_line", "1 regression, 0 improvements")
    return OutcomeSummary(**kw)
