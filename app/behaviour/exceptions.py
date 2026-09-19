"""
Behaviour QA Engine Exceptions.
"""


class BehaviourEngineError(Exception):
    """Base exception for all Behaviour Engine errors."""
    pass


class InvalidBehaviourCheckTypeError(BehaviourEngineError):
    """Raised when a non-BEHAVIOUR check is passed to BehaviourEngine."""
    pass


class CriticalBehaviourCheckError(BehaviourEngineError):
    """Raised if a behaviour check is unexpectedly configured as critical."""
    pass


class UnsupportedBehaviourCategoryError(BehaviourEngineError):
    """Raised when criteria does not specify a recognized behaviour category."""
    pass


class MetricCalculationError(BehaviourEngineError):
    """Raised when deterministic timing metric calculation encounters invalid data."""
    pass
