"""Rich review panel — display wizard answers before writing."""

from __future__ import annotations

from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from thesean.cli.wizard.models import ChangeType, InitAnswers


def display_review(answers: InitAnswers) -> None:
    """Print a Rich panel summarizing all wizard answers."""
    console = Console()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")

    table.add_row("Adapter", answers.adapter_name)
    table.add_row("Repo", str(answers.repo))
    table.add_row("Baseline weight", answers.baseline_weight.name)
    table.add_row("Candidate weight", answers.candidate_weight.name)
    table.add_row("Change type", answers.change_type.value.replace("_", " "))
    table.add_row("Environment", answers.env_id)
    table.add_row("Episodes", str(answers.num_episodes))
    table.add_row("Seed", str(answers.seed))

    # Show planner diff if relevant
    if answers.change_type in (ChangeType.PLANNER_ONLY, ChangeType.BOTH):
        diff_lines = []
        for key in answers.baseline_planner_config:
            base_val = answers.baseline_planner_config[key]
            cand_val = answers.candidate_planner_config.get(key, base_val)
            if base_val != cand_val:
                diff_lines.append(f"  {key}: {base_val} -> {cand_val}")
            else:
                diff_lines.append(f"  {key}: {base_val}")
        table.add_row("Planner config", "\n".join(diff_lines))
    else:
        table.add_row("Planner config", "(using defaults)")

    console.print()
    console.print(Panel(table, title="TheSean Init Review", border_style="cyan"))
    console.print()


def confirm_write() -> bool:
    """Ask user to confirm before writing files."""
    return inquirer.confirm(  # type: ignore[no-any-return]
        message="Write config and manifests?",
        default=True,
    ).execute()
