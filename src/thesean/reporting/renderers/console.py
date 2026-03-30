"""Print a console report from a ReportBundle using Rich."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from thesean.reporting.types import ReportBundle


def print_console_bundle(bundle: ReportBundle) -> None:
    console = Console()
    table = Table(title="TheSean findings")
    table.add_column("Metric")
    table.add_column("Status")
    table.add_column("Δ badness")
    table.add_column("Adj. p")

    for metric in bundle.compare.metrics:
        table.add_row(
            metric.metric_id,
            metric.status,
            f"{metric.delta_badness:+.4f}",
            "—" if metric.p_value_adj is None else f"{metric.p_value_adj:.3f}",
        )

    console.print(table)
