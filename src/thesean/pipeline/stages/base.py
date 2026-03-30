"""Stage protocol for the pipeline runner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from thesean.pipeline.state import StageResult

if TYPE_CHECKING:
    from thesean.pipeline.context import RunContext


class Stage(Protocol):
    name: str
    requires: tuple[str, ...]

    def is_up_to_date(self, ctx: RunContext) -> bool: ...
    def run(self, ctx: RunContext) -> StageResult: ...
