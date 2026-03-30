"""Core comparison logic: run both conditions, compute metrics, classify."""

from __future__ import annotations

import math
from pathlib import Path

from thesean.core.contracts import AdapterFactory
from thesean.models import RunManifest
from thesean.models.comparison import ComparisonReport, MetricComparison
from thesean.pipeline.compare.decision import classify_metric
from thesean.pipeline.compare.execution import run_condition
from thesean.pipeline.compare.stats import adjust_pvalues, bootstrap_ci, paired_pvalue


def compare_manifests(
    baseline_manifest: RunManifest,
    candidate_manifest: RunManifest,
    workspace: Path,
    factory: AdapterFactory,
    n_resamples: int = 5000,
    alpha: float = 0.05,
) -> ComparisonReport:
    """Run both conditions, compute metrics, classify each metric."""
    baseline_dir = workspace / "baseline"
    candidate_dir = workspace / "candidate"

    _, baseline_metrics = run_condition(baseline_manifest, baseline_dir, factory)
    _, candidate_metrics = run_condition(candidate_manifest, candidate_dir, factory)

    baseline_by_id = {m.metric_id: m for m in baseline_metrics}
    candidate_by_id = {m.metric_id: m for m in candidate_metrics}
    metric_ids = sorted(set(baseline_by_id) & set(candidate_by_id))

    raw_rows: list[dict[str, str | float | bool | list[float] | None]] = []
    pvals: list[float] = []

    for metric_id in metric_ids:
        b = baseline_by_id[metric_id]
        c = candidate_by_id[metric_id]

        delta = float(c.value - b.value)
        delta_badness = -delta if b.higher_is_better else delta

        raw_ci_low, raw_ci_high = bootstrap_ci(
            b.per_episode, c.per_episode, n_resamples=n_resamples
        )
        ci_low: float | None = None if math.isnan(raw_ci_low) else raw_ci_low
        ci_high: float | None = None if math.isnan(raw_ci_high) else raw_ci_high
        p_value = paired_pvalue(
            b.per_episode, c.per_episode, n_resamples=n_resamples
        )

        raw_rows.append(
            {
                "metric_id": metric_id,
                "baseline_value": float(b.value),
                "candidate_value": float(c.value),
                "delta": delta,
                "delta_badness": float(delta_badness),
                "higher_is_better": bool(b.higher_is_better),
                "baseline_per_episode": [float(x) for x in b.per_episode],
                "candidate_per_episode": [float(x) for x in c.per_episode],
                "ci_low": ci_low,
                "ci_high": ci_high,
                "p_value": p_value,
            }
        )
        pvals.append(p_value)

    adj = adjust_pvalues(pvals, alpha=alpha) if pvals else []

    metrics: list[MetricComparison] = []
    for row, p_adj in zip(raw_rows, adj, strict=False):
        status = classify_metric(
            delta_badness=float(row["delta_badness"]),  # type: ignore[arg-type]
            ci_low=row["ci_low"],  # type: ignore[arg-type]
            ci_high=row["ci_high"],  # type: ignore[arg-type]
            p_adj=p_adj,
            alpha=alpha,
        )
        metrics.append(
            MetricComparison(
                **row,  # type: ignore[arg-type]
                p_value_adj=p_adj,
                significant=bool(p_adj < alpha),
                status=status,
            )
        )

    return ComparisonReport(
        baseline_run_dir=str(baseline_dir),
        candidate_run_dir=str(candidate_dir),
        metrics=metrics,
    )
