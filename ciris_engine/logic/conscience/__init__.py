"""conscience components."""

from .interface import ConscienceInterface
from .registry import conscienceRegistry
from .core import (
    Entropyconscience,
    Coherenceconscience,
    OptimizationVetoconscience,
    EpistemicHumilityconscience,
)
from .thought_depth_guardrail import ThoughtDepthconscience

__all__ = [
    "ConscienceInterface",
    "conscienceRegistry",
    "Entropyconscience",
    "Coherenceconscience",
    "OptimizationVetoconscience",
    "EpistemicHumilityconscience",
    "ThoughtDepthconscience",
]
