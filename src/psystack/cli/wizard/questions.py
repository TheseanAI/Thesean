"""InquirerPy prompt functions — one function per wizard step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from InquirerPy import inquirer
from InquirerPy.validator import PathValidator

from psystack.cli.wizard.models import ChangeType


def prompt_adapter(available: list[str]) -> str:
    """Select adapter from registered adapters."""
    if len(available) == 1:
        return available[0]
    return inquirer.select(  # type: ignore[no-any-return]
        message="Adapter type:",
        choices=available,
        default=available[0],
    ).execute()


def prompt_repo() -> Path:
    """Prompt for adapter repo path with directory validation."""
    raw = inquirer.filepath(
        message="Path to adapter repo:",
        validate=PathValidator(is_dir=True, message="Directory not found"),
        only_directories=True,
    ).execute()
    return Path(raw).expanduser().resolve()


def prompt_weights(weights: list[dict[str, Any]], role: str, default_idx: int) -> int:
    """Select a weight file by index. role is 'Baseline' or 'Candidate'."""
    if len(weights) == 1:
        return 0

    choices = [
        {"name": f"{w['name']}  ({w['size_mb']} MB, {w['mtime']})", "value": i}
        for i, w in enumerate(weights)
    ]
    return inquirer.select(  # type: ignore[no-any-return]
        message=f"{role} weight:",
        choices=choices,
        default=default_idx,
    ).execute()


def prompt_change_type() -> ChangeType:
    """Select what changed between baseline and candidate."""
    choices = [
        {"name": "Weights only", "value": ChangeType.WEIGHTS_ONLY},
        {"name": "Planner config only", "value": ChangeType.PLANNER_ONLY},
        {"name": "Both weights and planner config", "value": ChangeType.BOTH},
        {"name": "Other / not sure", "value": ChangeType.OTHER},
    ]
    return inquirer.select(  # type: ignore[no-any-return]
        message="What changed between baseline and candidate?",
        choices=choices,
        default=ChangeType.WEIGHTS_ONLY,
    ).execute()


def prompt_planner_config(defaults: dict[str, Any]) -> dict[str, Any]:
    """Key-by-key prompts for candidate planner config values."""
    result: dict[str, Any] = {}
    for key, default_val in defaults.items():
        raw = inquirer.text(
            message=f"  {key}:",
            default=_serialize_value(default_val),
            validate=lambda val, dv=default_val: _validate_coerce(val, dv) is not None,
            invalid_message="Invalid value for this type",
        ).execute()
        result[key] = _coerce_value(raw, default_val)
    return result


def prompt_env(envs: list[str]) -> str:
    """Select environment. Defaults to Monza if present."""
    default = envs[0]
    for e in envs:
        if e.lower() == "monza":
            default = e
            break
    return inquirer.select(  # type: ignore[no-any-return]
        message="Environment:",
        choices=envs,
        default=default,
    ).execute()


def prompt_episodes() -> int:
    """Prompt for number of episodes."""
    raw = inquirer.text(
        message="Number of episodes:",
        default="20",
        validate=lambda val: val.strip().isdigit() and int(val.strip()) > 0,
        invalid_message="Must be a positive integer",
    ).execute()
    return int(raw.strip())


# --- Value coercion helpers ---


def _serialize_value(val: Any) -> str:
    """Serialize a config value to a string for display as a prompt default."""
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, list | dict):
        return json.dumps(val)
    return str(val)


def _coerce_value(raw: str, default_val: Any) -> Any:
    """Coerce a raw string input to match the type of the default value."""
    raw = raw.strip()
    result = _validate_coerce(raw, default_val)
    if result is not None:
        return result
    # Fallback: return as string
    return raw


def _validate_coerce(raw: str, default_val: Any) -> Any | None:
    """Try to coerce raw string to match default_val's type. Returns None on failure."""
    raw = raw.strip()
    if raw == "":
        return default_val

    if default_val is None:
        # Accept "null" or try JSON parse
        if raw.lower() == "null":
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return raw

    if isinstance(default_val, bool):
        if raw.lower() in ("true", "1", "yes"):
            return True
        if raw.lower() in ("false", "0", "no"):
            return False
        return None

    if isinstance(default_val, int):
        try:
            return int(raw)
        except ValueError:
            return None

    if isinstance(default_val, float):
        try:
            return float(raw)
        except ValueError:
            return None

    if isinstance(default_val, list | dict):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, type(default_val)):
                return parsed
            return None
        except (json.JSONDecodeError, ValueError):
            return None

    # str or unknown — accept as-is
    return raw
