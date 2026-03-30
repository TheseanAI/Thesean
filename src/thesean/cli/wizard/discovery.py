"""Pure discovery helpers — raise WizardDiscoveryError on failure, never typer.Exit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from thesean.adapters.registry import (
    AdapterLoadError,
    discover_adapter_factories,
    load_adapter_factory,
)
from thesean.core.contracts import AdapterFactory


class WizardDiscoveryError(RuntimeError):
    pass


def discover_adapters() -> list[str]:
    """Return sorted list of registered adapter names."""
    adapters = sorted(discover_adapter_factories().keys())
    if not adapters:
        raise WizardDiscoveryError("No adapters are installed.")
    return adapters


def load_factory(name: str) -> AdapterFactory:
    """Load and return an adapter factory by name."""
    try:
        return load_adapter_factory(name)
    except AdapterLoadError as e:
        raise WizardDiscoveryError(str(e)) from e


def discover_weights(factory: AdapterFactory, repo: Path) -> list[dict[str, Any]]:
    """Discover weight files via the factory. Raises if none found."""
    weights = factory.discover_weights(repo)
    if not weights:
        raise WizardDiscoveryError(
            f"No weight files found in {repo}. "
            "Check that the repo path is correct and contains model checkpoints."
        )
    return weights


def discover_envs(factory: AdapterFactory, repo: Path) -> list[str]:
    """Discover environments via the factory. Raises if none found."""
    envs = factory.discover_envs(repo)
    if not envs:
        raise WizardDiscoveryError(
            f"No environments found in {repo}. "
            "Check that the repo path contains environment configs."
        )
    return envs


def get_planner_defaults(factory: AdapterFactory) -> dict[str, Any]:
    """Return the adapter's default planner config."""
    return factory.default_planner_config()


def get_env_config(factory: AdapterFactory, env_id: str) -> dict[str, Any]:
    """Return the adapter's env config for a given env ID. No path normalization."""
    return factory.default_env_config(env_id)
