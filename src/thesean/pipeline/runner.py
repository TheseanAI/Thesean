"""Stage runner — orchestrates pipeline stages with progress display."""

from __future__ import annotations

import contextlib
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from thesean.pipeline.context import RunContext
from thesean.pipeline.stages.base import Stage
from thesean.pipeline.state import StageResult


@runtime_checkable
class StageObserver(Protocol):
    def on_stage_start(self, name: str) -> None: ...
    def on_stage_complete(self, name: str, result: StageResult) -> None: ...
    def on_stage_fail(self, name: str, error: str) -> None: ...
    def on_stage_skip(self, name: str, reason: str) -> None: ...
    def on_stage_reuse(self, name: str) -> None: ...


class _NullObserver:
    """Default no-op observer for CLI usage."""
    def on_stage_start(self, name: str) -> None: pass
    def on_stage_complete(self, name: str, result: StageResult) -> None: pass
    def on_stage_fail(self, name: str, error: str) -> None: pass
    def on_stage_skip(self, name: str, reason: str) -> None: pass
    def on_stage_reuse(self, name: str) -> None: pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_stages(
    ctx: RunContext,
    stages: Sequence[Stage],
    *,
    observer: StageObserver | None = None,
) -> None:
    obs = observer or _NullObserver()
    all_names = [stage.name for stage in stages]

    # Only use Rich Progress when no observer (CLI mode)
    progress_ctx: Any
    if observer is None:
        from rich.progress import Progress
        progress_ctx = Progress()
    else:
        progress_ctx = contextlib.nullcontext()

    with progress_ctx as progress:
        if progress is not None:
            task_id = progress.add_task("Thesean pipeline", total=len(stages))

        for stage in stages:
            # 1. Explicit skip
            if stage.name in ctx.skip:
                reason = "explicitly skipped"
                ctx.mark_skipped(stage.name, reason=reason)
                ctx.save_state()
                obs.on_stage_skip(stage.name, reason)
                if progress is not None:
                    progress.advance(task_id)
                continue

            # 2. Outside selected range — preserves existing completed state
            if not ctx.stage_selected(stage.name, all_names):
                reason = "outside selected range"
                ctx.mark_skipped(stage.name, reason=reason)
                ctx.save_state()
                obs.on_stage_skip(stage.name, reason)
                if progress is not None:
                    progress.advance(task_id)
                continue

            # 3. Dependency check
            if not ctx.prereqs_satisfied(stage.requires):
                raise RuntimeError(
                    f"Stage '{stage.name}' requires completed stages: {stage.requires}"
                )

            # 4. Resume: reuse if up-to-date — keeps completed status
            if ctx.resume and stage.is_up_to_date(ctx):
                ctx.mark_reused(stage.name)
                ctx.save_state()
                obs.on_stage_reuse(stage.name)
                if progress is not None:
                    progress.advance(task_id)
                continue

            # 5. Run — fail fast on exception
            try:
                ctx.mark_running(stage.name, started_at=utc_now())
                obs.on_stage_start(stage.name)
                result = stage.run(ctx)
                ctx.mark_completed(stage.name, result=result, finished_at=utc_now())
                obs.on_stage_complete(stage.name, result)
            except Exception as exc:
                ctx.mark_failed(stage.name, error=str(exc), finished_at=utc_now())
                ctx.save_state()
                obs.on_stage_fail(stage.name, str(exc))
                raise
            else:
                ctx.save_state()
                if progress is not None:
                    progress.advance(task_id)
