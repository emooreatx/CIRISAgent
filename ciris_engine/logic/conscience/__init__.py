"""conscience components."""

from .interface import ConscienceInterface
from .registry import conscienceRegistry
from .core import (
    EntropyConscience,
    CoherenceConscience,
    OptimizationVetoConscience,
    EpistemicHumilityConscience,
)
from .thought_depth_guardrail import ThoughtDepthGuardrail

__all__ = [
    "ConscienceInterface",
    "conscienceRegistry",
    "EntropyConscience",
    "CoherenceConscience",
    "OptimizationVetoConscience",
    "EpistemicHumilityConscience",
    "ThoughtDepthGuardrail",
]
