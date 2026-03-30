"""Event detection engine — divergence detection from episode data."""

from thesean.pipeline.events.config import EventDetectionConfig
from thesean.pipeline.events.detection import detect_events

__all__ = ["EventDetectionConfig", "detect_events"]
