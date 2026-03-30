"""Materialize an evidence pack from a ReportBundle."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from thesean.models.evidence import EvidencePack
from thesean.reporting.types import ReportBundle


def materialize_evidence_pack_from_bundle(bundle: ReportBundle) -> EvidencePack:
    """Build an EvidencePack entirely from a ReportBundle — no workspace reads."""
    return EvidencePack(
        pack_id=f"pack_{uuid.uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        summary=(
            f"{bundle.summary.total_metrics} metrics, "
            f"{bundle.summary.regressions} regressions, "
            f"{bundle.summary.improvements} improvements, "
            f"{bundle.summary.no_change} no-change"
        ),
        baseline_manifest=bundle.baseline_manifest,
        candidate_manifest=bundle.candidate_manifest,
        compare=bundle.compare,
        isolation=bundle.isolation,
        attributions=bundle.attribution,
    )
