"""EventStage — detect divergence events from compare output episode data."""

from __future__ import annotations

import json

from thesean.pipeline.context import RunContext
from thesean.pipeline.events.config import EventDetectionConfig
from thesean.pipeline.events.detection import detect_events
from thesean.pipeline.state import StageResult


class EventStage:
    name = "events"
    requires = ("compare",)

    def is_up_to_date(self, ctx: RunContext) -> bool:
        events_path = ctx.stage_output_dir / "events.json"
        return events_path.exists()

    def run(self, ctx: RunContext) -> StageResult:
        # Load episode data from compare stage output directory
        baseline_episodes = self._load_episodes(ctx, "baseline")
        candidate_episodes = self._load_episodes(ctx, "candidate")

        # Load event config from settings if available
        config = EventDetectionConfig()
        settings = ctx.settings
        if hasattr(settings, "event") and settings.event is not None:
            config = EventDetectionConfig.model_validate(
                settings.event.model_dump()
            )

        events = detect_events(baseline_episodes, candidate_episodes, config)

        events_path = ctx.stage_output_dir / "events.json"
        events_data = [e.model_dump() for e in events]
        events_path.write_text(json.dumps(events_data, indent=2))

        event_types = [e.type for e in events]
        return StageResult(
            primary_output=str(events_path),
            output_paths=[str(events_path)],
            summary=f"{len(events)} events detected: {', '.join(set(event_types)) or 'none'}",
            metadata={"num_events": len(events), "event_types": list(set(event_types))},
        )

    def _load_episodes(self, ctx: RunContext, condition: str) -> list[dict]:
        """Load episode data from the compare stage output."""
        episodes_path = ctx.workspace / condition / "episodes.json"
        if episodes_path.exists():
            return json.loads(episodes_path.read_text())  # type: ignore[no-any-return]
        return []
