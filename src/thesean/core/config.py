"""Thesean settings: Pydantic-backed config with workspace-explicit loading."""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# TOML reading: stdlib tomllib (3.11+) with tomli fallback (3.10)
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


class AdapterSettings(BaseModel):
    type: str = Field(..., description="Adapter name, e.g. 'f1'")
    repo: Path


class RunDefaults(BaseModel):
    episodes: int = 20
    alpha: float = 0.05
    effect_threshold: float = 0.01
    bootstrap_resamples: int = 5000


class EventSettings(BaseModel):
    threshold: float = 0.15
    persistence_k: int = 4
    signal_weights: dict[str, float] = Field(default_factory=lambda: {
        "steering_delta": 0.25,
        "throttle_delta": 0.15,
        "brake_delta": 0.10,
        "heading_delta": 0.20,
        "speed_delta": 0.10,
        "progress_delta": 0.10,
        "reward_delta": 0.10,
    })
    active_signals: list[str] | None = None
    action_threshold: float = 0.3
    risk_threshold: float = 3.0
    boundary_threshold: float = 0.15


class TheseanSettings(BaseSettings):
    adapter: AdapterSettings
    run: RunDefaults = RunDefaults()
    event: EventSettings = EventSettings()

    model_config = SettingsConfigDict(extra="forbid")


def load_settings_from_workspace(workspace: Path) -> TheseanSettings:
    """Load and validate settings from an explicit workspace directory."""
    workspace = workspace.expanduser().resolve()
    config_path = workspace / "thesean.toml"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config file: {config_path}")
    if tomllib is None:
        raise ImportError(
            "Python 3.10 requires the 'tomli' package to read TOML. "
            "Install it with: pip install tomli"
        )
    with config_path.open("rb") as f:
        raw = tomllib.load(f)
    settings = TheseanSettings.model_validate(raw)
    # Normalize adapter repo relative to workspace if needed
    repo = settings.adapter.repo
    if not repo.is_absolute():
        settings.adapter.repo = (workspace / repo).resolve()
    return settings
