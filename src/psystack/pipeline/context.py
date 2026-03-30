"""RunContext — centralizes all execution-time loading and path logic."""

from __future__ import annotations

from pathlib import Path

from psystack.adapters.registry import load_adapter_factory
from psystack.core.config import load_settings_from_workspace
from psystack.core.contracts import AdapterFactory
from psystack.models.case import Case
from psystack.pipeline.state import RunState, StageResult, StageState


class StageNameError(ValueError):
    """Raised when --from, --to, or --skip references an unknown stage name."""
    pass


class RunContext:
    def __init__(
        self,
        workspace: Path,
        *,
        resume: bool = False,
        from_stage: str | None = None,
        to_stage: str | None = None,
        skip: set[str] | None = None,
        pipeline_names: tuple[str, ...] = (),
    ) -> None:
        self.workspace = workspace.expanduser().resolve()
        self.resume = resume
        self.from_stage = from_stage
        self.to_stage = to_stage
        self.skip = skip or set()

        # Validate stage names before heavy loading
        if pipeline_names:
            self._validate_stage_range(pipeline_names)

        # Load settings and bind adapter
        self.settings = load_settings_from_workspace(self.workspace)
        self.factory: AdapterFactory = load_adapter_factory(self.settings.adapter.type)
        self.factory.bind_repo(self.settings.adapter.repo)

        # Load case and derive manifests
        self.case = Case.model_validate_json(
            (self.workspace / "case.json").read_text()
        )
        self.baseline_manifest = self.case.run_a.to_manifest()
        self.candidate_manifest = self.case.run_b.to_manifest() if self.case.run_b else self.case.run_a.to_manifest()

        # Patch episode count from case (not planner horizon)
        self.baseline_manifest.num_episodes = self.case.episode_count
        self.candidate_manifest.num_episodes = self.case.episode_count

        # Resolve env_config if empty (builder stores on case, not on run)
        if self.case.track_ref and not self.baseline_manifest.env_config:
            # Infer raster_size from world model checkpoints when available
            wm_a = wm_b = None
            try:
                wm_a = self.factory.create_world_model(self.case.run_a.world_model_ref)
                if self.case.run_b:
                    wm_b = self.factory.create_world_model(self.case.run_b.world_model_ref)
            except Exception:
                pass  # fall back to default raster_size
            base_env_a = self.factory.default_env_config(self.case.track_ref, world_model=wm_a)
            base_env_b = self.factory.default_env_config(self.case.track_ref, world_model=wm_b or wm_a)
            if self.case.shared_env_overrides:
                base_env_a.update(self.case.shared_env_overrides)
                base_env_b.update(self.case.shared_env_overrides)
            self.baseline_manifest.env_config = base_env_a
            self.candidate_manifest.env_config = base_env_b

        # Stage output directory
        self.stage_output_dir = self.workspace / "stage_outputs"
        self.stage_output_dir.mkdir(parents=True, exist_ok=True)

        # Run state
        self.state_path = self.workspace / "run_state.json"
        self.state = self._load_or_init_state()

    def _validate_stage_range(self, names: tuple[str, ...]) -> None:
        """Validate --from/--to/--skip against known pipeline stage names."""
        name_set = set(names)
        if self.from_stage and self.from_stage not in name_set:
            raise StageNameError(
                f"Unknown stage '{self.from_stage}' in --from. "
                f"Available stages: {', '.join(names)}"
            )
        if self.to_stage and self.to_stage not in name_set:
            raise StageNameError(
                f"Unknown stage '{self.to_stage}' in --to. "
                f"Available stages: {', '.join(names)}"
            )
        for item in self.skip:
            if item not in name_set:
                raise StageNameError(
                    f"Unknown stage '{item}' in --skip. "
                    f"Available stages: {', '.join(names)}"
                )
        if self.from_stage and self.to_stage:
            ordered = list(names)
            if ordered.index(self.from_stage) > ordered.index(self.to_stage):
                raise StageNameError(
                    f"--from '{self.from_stage}' comes after --to '{self.to_stage}'. "
                    f"Stage order: {', '.join(names)}"
                )

    def _load_or_init_state(self) -> RunState:
        # Always load existing state if present — needed for:
        # - --resume: reuse up-to-date stages
        # - --from/--to: know prior stages completed for dependency checks
        # - standalone commands (isolate, report): verify prerequisites
        if self.state_path.exists():
            return RunState.model_validate_json(self.state_path.read_text())
        return RunState()

    def save_state(self) -> None:
        self.state_path.write_text(self.state.model_dump_json(indent=2))

    def output_path(self, stage_name: str) -> Path:
        return self.stage_output_dir / f"{stage_name}.json"

    # --- Stage selection ---

    def stage_selected(self, name: str, all_names: list[str]) -> bool:
        """Check if stage is within --from/--to range."""
        if self.from_stage is None and self.to_stage is None:
            return True
        idx = all_names.index(name)
        start = all_names.index(self.from_stage) if self.from_stage else 0
        end = all_names.index(self.to_stage) if self.to_stage else len(all_names) - 1
        return start <= idx <= end

    def prereqs_satisfied(self, requires: tuple[str, ...]) -> bool:
        """Check that all required stages have completed (including reused)."""
        for req in requires:
            state = self.state.stages.get(req)
            if state is None or state.status != "completed":
                return False
        return True

    # --- State transitions ---

    def mark_running(self, name: str, started_at: str) -> None:
        existing = self.state.stages.get(name)
        self.state.stages[name] = StageState(
            name=name,
            status="running",
            started_at=started_at,
            result=existing.result if existing else None,
        )

    def mark_completed(self, name: str, result: StageResult, finished_at: str) -> None:
        self.state.stages[name] = StageState(
            name=name,
            status="completed",
            result=result,
            finished_at=finished_at,
            reused=False,
        )

    def mark_failed(self, name: str, error: str, finished_at: str) -> None:
        existing = self.state.stages.get(name)
        self.state.stages[name] = StageState(
            name=name,
            status="failed",
            error=error,
            finished_at=finished_at,
            started_at=existing.started_at if existing else None,
            result=existing.result if existing else None,
        )

    def mark_skipped(self, name: str, reason: str) -> None:
        """Mark a stage as skipped. Never overwrites an existing completed state."""
        existing = self.state.stages.get(name)
        if existing and existing.status == "completed":
            return
        self.state.stages[name] = StageState(
            name=name,
            status="skipped",
            error=reason,
        )

    def mark_reused(self, name: str) -> None:
        """Mark an already-completed stage as reused, or synthesize a completed
        state if the artifact exists but run_state.json didn't contain it."""
        existing = self.state.stages.get(name)
        if existing and existing.status == "completed":
            existing.reused = True
            return
        # Synthesize completed state from existing artifacts
        output = self.output_path(name)
        self.state.stages[name] = StageState(
            name=name,
            status="completed",
            reused=True,
            result=StageResult(
                primary_output=str(output) if output.exists() else None,
                output_paths=[str(output)] if output.exists() else [],
                summary="Reused existing stage output",
                metadata={"synthetic": True},
            ),
        )
