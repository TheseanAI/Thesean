"""Thin UI state — cached backend data + selection state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from thesean.models.case import Case
from thesean.models.comparison import ComparisonReport
from thesean.models.episode import OutcomeSummary
from thesean.models.event import Event
from thesean.models.isolation import AttributionTable, IsolationResultBundle
from thesean.models.project import Project
from thesean.reporting.types import ReportBundle
from thesean.tui.detection import DetectedContext


class CaseState(str, Enum):
    """Lifecycle states for a Case per D-06."""

    DRAFT = "draft"
    RUNNING = "running"
    RUN_FAILED = "run_failed"
    RUN_COMPLETE = "run_complete"
    ANALYSIS_PARTIAL = "analysis_partial"
    READY = "ready"
    NEEDS_ATTENTION = "needs_attention"


class ScreenMode(str, Enum):
    """Display modes for InvestigationScreen — drives visibility, gating, timeline."""

    DRAFT_EMPTY = "draft_empty"
    RUNNING_LIVE = "running_live"
    READY_INVESTIGATION = "ready_investigation"
    ANALYSIS_FAILED = "analysis_failed"


def screen_mode_from_case_state(cs: CaseState) -> ScreenMode:
    """Map CaseState to the appropriate ScreenMode."""
    _MAP = {
        CaseState.DRAFT: ScreenMode.DRAFT_EMPTY,
        CaseState.RUNNING: ScreenMode.RUNNING_LIVE,
        CaseState.RUN_FAILED: ScreenMode.DRAFT_EMPTY,
        CaseState.RUN_COMPLETE: ScreenMode.RUNNING_LIVE,  # analysis still pending
        CaseState.ANALYSIS_PARTIAL: ScreenMode.ANALYSIS_FAILED,
        CaseState.READY: ScreenMode.READY_INVESTIGATION,
        CaseState.NEEDS_ATTENTION: ScreenMode.READY_INVESTIGATION,
    }
    return _MAP.get(cs, ScreenMode.DRAFT_EMPTY)


@dataclass
class RuntimeStatus:
    mode: Literal[
        "idle",
        "loading_case",
        "creating_case",
        "running_compare",
        "running_isolate",
        "running_attribute",
        "running_report",
        "eval_running_a",
        "eval_running_b",
        "eval_computing",
        "complete",
        "error",
    ] = "idle"
    current_stage: str | None = None
    message: str = ""
    error: str | None = None
    eval_episode: int = 0
    eval_total: int = 0


@dataclass
class AppState:
    # Context detection
    detected_context: DetectedContext = field(default_factory=DetectedContext)

    # Workspace
    current_workspace: Path | None = None
    workspace_loaded: bool = False
    active_layout: str = "home"
    case_name: str = ""
    case_state: CaseState = CaseState.DRAFT

    # Cached backend data (loaded once per workspace open)
    compare_report: ComparisonReport | None = None
    isolation_bundle: IsolationResultBundle | None = None
    attributions: list[AttributionTable] = field(default_factory=list)
    report_bundle: ReportBundle | None = None

    # New domain models (Phase 4)
    project: Project | None = None
    case: Case | None = None
    events: list[Event] = field(default_factory=list)
    outcomes: OutcomeSummary | None = None

    # Selection state
    selected_metric_id: str | None = None
    selected_isolation_case_id: str | None = None
    selected_artifact_path: str | None = None
    current_step: int = 0
    current_event_idx: int = 0

    # Episode selection (Phase 3 — D-04)
    selected_run_id: str | None = None       # e.g., "ep_0002" — active episode ID
    selected_episode_idx: int = 0            # 0-based index into episode list
    episode_count: int = 0                   # total episodes per side

    # Adapter (Phase 7 — adapter-agnostic threading)
    signal_translator: Any = None   # SignalTranslator | None
    signal_schema: Any = None       # SignalSchema | None

    # Track geometry (for braille track map progress bars)
    track_geometry: list[tuple[float, float]] | None = None

    # Live monitoring mode ("sidecar"/"both" disabled — pygame sidecar is buggy)
    live_view: Literal["none", "tui", "sidecar", "both"] = "tui"

    # Runtime status (replaces run_in_progress / current_stage_name / last_error)
    runtime: RuntimeStatus = field(default_factory=RuntimeStatus)

    @property
    def run_in_progress(self) -> bool:
        return self.runtime.mode not in ("idle", "complete", "error")

    @property
    def current_stage_name(self) -> str | None:
        return self.runtime.current_stage

    @property
    def last_error(self) -> str | None:
        return self.runtime.error
