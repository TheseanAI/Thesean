"""Workspace directory structure and state management.

Workspace layout (D-01, D-02):
    .thesean/cases/{case-id}/
        case.json           # Frozen case definition (immutable after build)
        thesean.toml        # Adapter/repo binding metadata
        workspace_state.json # Mutable state (case_state, attempt history)
        runs/
            a/
                episodes.json
            b/
                episodes.json
        analysis/
            outcomes.json
            events.json
        attempts/
            {attempt-id}.json
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# -- Error Categories (D-07) --
# These document the 5 error categories from D-07. Used as the error_category
# argument to save_failed_attempt(). Callers should use these constants rather
# than raw strings for consistency.

ERR_CASE_REFERENCE = "case_reference"
"""(1) Case/reference errors: missing weights, track, bad policy ref, stale binding."""

ERR_STARTUP_ENV = "startup_env"
"""(2) Startup/env errors: adapter import, dependency, env creation, track load."""

ERR_MID_RUN = "mid_run"
"""(3) Mid-run execution errors: policy/planner/model crash, env.step crash."""

ERR_ANALYSIS = "analysis"
"""(4) Analysis errors: run succeeded but outcomes/signals/events computation failed."""

ERR_WORKSPACE_DRIFT = "workspace_drift"
"""(5) Workspace drift on reopen: repo changed, refs stale."""

ERROR_CATEGORIES = frozenset({
    ERR_CASE_REFERENCE,
    ERR_STARTUP_ENV,
    ERR_MID_RUN,
    ERR_ANALYSIS,
    ERR_WORKSPACE_DRIFT,
})
"""All valid error categories per D-07."""


def create_workspace_dirs(workspace: Path) -> None:
    """Create the workspace directory structure.

    Creates: workspace/, runs/a/, runs/b/, analysis/, attempts/
    """
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "runs" / "a").mkdir(parents=True, exist_ok=True)
    (workspace / "runs" / "b").mkdir(parents=True, exist_ok=True)
    (workspace / "analysis").mkdir(parents=True, exist_ok=True)
    (workspace / "attempts").mkdir(parents=True, exist_ok=True)


def read_workspace_state(workspace: Path) -> dict[str, Any]:
    """Read workspace_state.json. Returns default state if missing."""
    state_path = workspace / "workspace_state.json"
    if state_path.exists():
        return json.loads(state_path.read_text())  # type: ignore[no-any-return]
    return {"case_state": "draft", "attempts": []}


def write_workspace_state(workspace: Path, state: dict[str, Any]) -> None:
    """Write workspace_state.json."""
    state_path = workspace / "workspace_state.json"
    state_path.write_text(json.dumps(state, indent=2))


def update_case_state(workspace: Path, new_state: str) -> None:
    """Update just the case_state field in workspace_state.json."""
    ws_state = read_workspace_state(workspace)
    ws_state["case_state"] = new_state
    write_workspace_state(workspace, ws_state)


def save_failed_attempt(
    workspace: Path,
    *,
    side: str | None,
    episode: int | None,
    step: int | None,
    error_category: str,
    error_message: str,
    stack_trace: str | None = None,
) -> str:
    """Save failure metadata to attempts/ directory (D-08).

    Args:
        error_category: One of the ERR_* constants defined above (D-07).
            Valid values: case_reference, startup_env, mid_run, analysis,
            workspace_drift.

    Returns the attempt_id.
    """
    attempt_id = uuid.uuid4().hex[:8]
    now = datetime.now(tz=timezone.utc).isoformat()

    attempt = {
        "attempt_id": attempt_id,
        "timestamp": now,
        "side": side,
        "episode": episode,
        "step": step,
        "error_category": error_category,
        "error_message": error_message,
        "stack_trace_path": None,
        "canonical": False,
    }

    # Save stack trace to file if provided
    if stack_trace:
        trace_path = workspace / "attempts" / f"{attempt_id}_trace.txt"
        trace_path.write_text(stack_trace)
        attempt["stack_trace_path"] = str(trace_path.name)

    # Save attempt metadata
    attempt_path = workspace / "attempts" / f"{attempt_id}.json"
    attempt_path.write_text(json.dumps(attempt, indent=2))

    # Update workspace state with attempt reference
    ws_state = read_workspace_state(workspace)
    ws_state.setdefault("attempts", []).append(attempt_id)
    write_workspace_state(workspace, ws_state)

    return attempt_id


def load_result(workspace: Path) -> dict[str, Any] | None:
    """Load analysis/result.json if it exists.

    Returns the parsed dict, or None if no result file.
    Callers can pass to EvaluationResult.model_validate() for typed access.
    """
    result_path = workspace / "analysis" / "result.json"
    if not result_path.exists():
        return None
    return json.loads(result_path.read_text())  # type: ignore[no-any-return]


class _NumpyEncoder(json.JSONEncoder):
    """Handle numpy scalars/arrays that slip through from env/planner outputs."""

    def default(self, o: Any) -> Any:
        try:
            import numpy as np
            if isinstance(o, np.floating):
                return float(o)
            if isinstance(o, np.integer):
                return int(o)
            if isinstance(o, np.ndarray):
                return o.tolist()
        except ImportError:
            pass
        return super().default(o)


def save_episodes(workspace: Path, side: str, episodes: list[dict[str, Any]]) -> Path:
    """Save episode data to runs/{side}/episodes.json."""
    out_path = workspace / "runs" / side / "episodes.json"
    out_path.write_text(json.dumps(episodes, indent=2, cls=_NumpyEncoder))
    return out_path
