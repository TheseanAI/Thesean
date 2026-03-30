from thesean.core.contracts import MetricPlugin

from .offtrack import OffTrackRateMetric
from .prediction_error import WorldModelPredictionError
from .progress import ProgressMetric
from .reward import CumulativeRewardMetric
from .survival import SurvivalStepsMetric

ALL_METRICS: list[MetricPlugin] = [
    ProgressMetric(),
    OffTrackRateMetric(),
    SurvivalStepsMetric(),
    CumulativeRewardMetric(),
    WorldModelPredictionError(),
]

__all__ = [
    "ProgressMetric",
    "OffTrackRateMetric",
    "SurvivalStepsMetric",
    "CumulativeRewardMetric",
    "WorldModelPredictionError",
    "ALL_METRICS",
]
