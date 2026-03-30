"""Init wizard orchestrator — the only place with CLI control flow."""

from __future__ import annotations

import sys
from pathlib import Path

import tomli_w
import typer

from thesean.cli.wizard import discovery, questions, review
from thesean.cli.wizard.discovery import WizardDiscoveryError
from thesean.cli.wizard.models import ChangeType, InitAnswers, WeightInfo
from thesean.models import RunManifest


def _ensure_interactive(auto_confirm: bool) -> None:
    """Exit early if not running in a terminal and --yes was not passed."""
    if auto_confirm:
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        typer.echo("Non-interactive terminal detected. Re-run with --yes.", err=True)
        raise typer.Exit(1)


def run_init_wizard(workspace: Path, auto_confirm: bool = False) -> None:
    """Interactive setup wizard: discover adapters/weights/envs, review, then write."""
    _ensure_interactive(auto_confirm)

    typer.echo("=== TheSean Init ===\n")

    # 1. Discover and select adapter
    try:
        available = discovery.discover_adapters()
    except WizardDiscoveryError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    adapter_name = questions.prompt_adapter(available)

    # 2. Prompt repo path
    repo = questions.prompt_repo()

    # 3. Load factory and bind repo
    try:
        factory = discovery.load_factory(adapter_name)
    except WizardDiscoveryError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    factory.bind_repo(repo)

    # 4. Discover weights
    try:
        weights = discovery.discover_weights(factory, repo)
    except WizardDiscoveryError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    typer.echo(f"\nFound {len(weights)} weight file(s):")
    for i, w in enumerate(weights):
        typer.echo(f"  [{i}] {w['name']}  ({w['size_mb']} MB, {w['mtime']})")
    if len(weights) == 1:
        typer.echo("\n  Only 1 weight found — it will be used for both baseline and candidate")
        typer.echo("  (useful when comparing planner config changes).")

    # 5. Select baseline and candidate weights
    baseline_idx = questions.prompt_weights(weights, "Baseline", default_idx=0)
    cand_default = (1 if baseline_idx == 0 else 0) if len(weights) > 1 else 0
    candidate_idx = questions.prompt_weights(weights, "Candidate", default_idx=cand_default)

    # 6. What changed?
    change_type = questions.prompt_change_type()

    # 7. Planner config
    baseline_planner = discovery.get_planner_defaults(factory)
    if change_type in (ChangeType.PLANNER_ONLY, ChangeType.BOTH):
        typer.echo("\nBaseline planner config (defaults):")
        for k, v in baseline_planner.items():
            typer.echo(f"  {k} = {v}")
        typer.echo("\nEnter candidate planner values (press Enter to keep default):")
        candidate_planner = questions.prompt_planner_config(baseline_planner)
    else:
        candidate_planner = dict(baseline_planner)

    # 8. Discover and select environment
    try:
        envs = discovery.discover_envs(factory, repo)
    except WizardDiscoveryError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    env_id = questions.prompt_env(envs)
    env_config = discovery.get_env_config(factory, env_id)

    # 9. Episodes
    num_episodes = questions.prompt_episodes()

    # 10. Build typed answers
    answers = InitAnswers(
        adapter_name=adapter_name,
        repo=repo,
        weights=[WeightInfo(**w) for w in weights],
        baseline_weight=WeightInfo(**weights[baseline_idx]),
        candidate_weight=WeightInfo(**weights[candidate_idx]),
        change_type=change_type,
        baseline_planner_config=baseline_planner,
        candidate_planner_config=candidate_planner,
        env_id=env_id,
        env_config=env_config,
        num_episodes=num_episodes,
    )

    # 11. Review and confirm
    if not auto_confirm:
        review.display_review(answers)
        if not review.confirm_write():
            typer.echo("Aborted.")
            raise typer.Exit(0)

    # 12. Write outputs
    _write_outputs(workspace, answers)


def write_workspace_files(workspace: Path, answers: InitAnswers) -> list[Path]:
    """Write thesean.toml and manifests. Returns list of written paths. No console output."""
    workspace.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    # Write thesean.toml
    toml_data = {
        "adapter": {
            "type": answers.adapter_name,
            "repo": str(answers.repo),
        },
        "run": {
            "episodes": answers.num_episodes,
        },
    }
    config_path = workspace / "thesean.toml"
    with config_path.open("wb") as f:
        tomli_w.dump(toml_data, f)
    written.append(config_path)

    # Write manifests
    baseline_manifest = RunManifest(
        run_id="baseline",
        description=f"Baseline: {answers.baseline_weight.name} on {answers.env_id}",
        world_model_weights=answers.baseline_weight.path,
        planner_config=answers.baseline_planner_config,
        env_config=answers.env_config,
        num_episodes=answers.num_episodes,
        seed=answers.seed,
    )
    candidate_manifest = RunManifest(
        run_id="candidate",
        description=f"Candidate: {answers.candidate_weight.name} on {answers.env_id}",
        world_model_weights=answers.candidate_weight.path,
        planner_config=answers.candidate_planner_config,
        env_config=answers.env_config,
        num_episodes=answers.num_episodes,
        seed=answers.seed,
    )

    for name, manifest in [
        ("baseline_manifest.json", baseline_manifest),
        ("candidate_manifest.json", candidate_manifest),
    ]:
        path = workspace / name
        path.write_text(manifest.model_dump_json(indent=2))
        written.append(path)

    return written


def _write_outputs(workspace: Path, answers: InitAnswers) -> None:
    """Original CLI version with typer.echo output."""
    paths = write_workspace_files(workspace, answers)
    for p in paths:
        typer.echo(f"Wrote {p}")
    typer.echo(f"\nDone! Next: thesean run --workspace {workspace}")
