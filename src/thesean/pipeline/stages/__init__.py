from thesean.pipeline.stages.attribute import AttributeStage
from thesean.pipeline.stages.compare import CompareStage
from thesean.pipeline.stages.events import EventStage
from thesean.pipeline.stages.isolate import IsolateStage
from thesean.pipeline.stages.report import ReportStage

DEFAULT_PIPELINE = (
    CompareStage(),
    EventStage(),
    IsolateStage(),
    AttributeStage(),
    ReportStage(),
)

__all__ = [
    "CompareStage",
    "EventStage",
    "IsolateStage",
    "AttributeStage",
    "ReportStage",
    "DEFAULT_PIPELINE",
]
