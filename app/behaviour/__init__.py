"""
Behaviour QA Engine Package.

Exposes models, metrics, engine, and exceptions for evaluating non-functional
conversational timing and conduct.
"""

from app.behaviour.engine import BehaviourEngine
from app.behaviour.exceptions import (
    BehaviourEngineError,
    CriticalBehaviourCheckError,
    InvalidBehaviourCheckTypeError,
    MetricCalculationError,
    UnsupportedBehaviourCategoryError,
)
from app.behaviour.metrics import BehaviourMetrics
from app.behaviour.models import (
    BehaviourCategory,
    CheckResult,
    CheckStatus,
    DeadAirIncident,
    InterruptionIncident,
)

__all__ = [
    "BehaviourEngine",
    "BehaviourMetrics",
    "BehaviourCategory",
    "DeadAirIncident",
    "InterruptionIncident",
    "CheckResult",
    "CheckStatus",
    "BehaviourEngineError",
    "InvalidBehaviourCheckTypeError",
    "CriticalBehaviourCheckError",
    "UnsupportedBehaviourCategoryError",
    "MetricCalculationError",
]
