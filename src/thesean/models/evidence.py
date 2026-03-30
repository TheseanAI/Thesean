from __future__ import annotations

from pydantic import BaseModel, Field

from .comparison import ComparisonReport
from .isolation import AttributionTable, IsolationResultBundle
from .manifest import RunManifest


class EvidencePack(BaseModel):
    pack_id: str
    created_at: str
    summary: str
    baseline_manifest: RunManifest
    candidate_manifest: RunManifest
    compare: ComparisonReport
    isolation: IsolationResultBundle | None = None
    attributions: list[AttributionTable] = Field(default_factory=list)
