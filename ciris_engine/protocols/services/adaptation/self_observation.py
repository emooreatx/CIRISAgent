"""
Protocol for Self-Observation Service - Pattern detection and learning.

This service observes system behavior, detects patterns, and stores insights
for the agent's autonomous adaptation within its identity bounds.
"""

from typing import List, Optional, Protocol, TYPE_CHECKING
from abc import abstractmethod

from ...runtime.base import ServiceProtocol

# Import forward references for schemas
if TYPE_CHECKING:
    from ciris_engine.schemas.infrastructure.feedback_loop import (
        DetectedPattern, AnalysisResult, PatternType
    )
    from ciris_engine.schemas.infrastructure.behavioral_patterns import (
        ActionFrequency, TemporalPattern
    )

class SelfObservationServiceProtocol(ServiceProtocol, Protocol):
    """
    Protocol for self-observation service.

    Implements continuous observation and pattern detection to enable
    autonomous adaptation through stored insights.
    """

    # ========== Pattern Detection ==========

    @abstractmethod
    async def analyze_patterns(
        self,
        force: bool = False
    ) -> "AnalysisResult":
        """
        Analyze recent system behavior and detect patterns.

        This is the main entry point that:
        1. Detects patterns from metrics and telemetry
        2. Stores pattern insights for agent introspection
        3. Updates learning state

        Args:
            force: Force analysis even if not due

        Returns:
            AnalysisResult with patterns detected and insights stored
        """
        ...

    @abstractmethod
    async def get_detected_patterns(
        self,
        pattern_type: Optional["PatternType"] = None,
        hours: int = 24
    ) -> List["DetectedPattern"]:
        """
        Get recently detected patterns.

        Args:
            pattern_type: Filter by pattern type (temporal, frequency, etc.)
            hours: Look back period

        Returns:
            List of detected patterns
        """
        ...

    @abstractmethod
    async def get_action_frequency(
        self,
        hours: int = 24
    ) -> dict[str, "ActionFrequency"]:
        """
        Get frequency analysis of agent actions.

        Args:
            hours: Analysis window

        Returns:
            Map of action -> frequency data
        """
        ...

    # ========== Pattern Insights ==========

    @abstractmethod
    async def get_pattern_insights(
        self,
        limit: int = 50
    ) -> List[dict]:
        """
        Get stored pattern insights.

        These are the insights stored in graph memory for the agent
        to use during its reasoning process.

        Args:
            limit: Maximum insights to return

        Returns:
            List of insight nodes from graph memory
        """
        ...

    @abstractmethod
    async def get_learning_summary(
        self
    ) -> dict:
        """
        Get summary of what the system has learned.

        Returns:
            Summary of patterns, frequencies, and adaptations
        """
        ...

    # ========== Temporal Analysis ==========

    @abstractmethod
    async def get_temporal_patterns(
        self,
        hours: int = 168  # 1 week
    ) -> List["TemporalPattern"]:
        """
        Get temporal patterns (daily, weekly cycles).

        Args:
            hours: Analysis window

        Returns:
            List of temporal patterns detected
        """
        ...

    # ========== Effectiveness Tracking ==========

    @abstractmethod
    async def get_pattern_effectiveness(
        self,
        pattern_id: str
    ) -> Optional[dict]:
        """
        Get effectiveness metrics for a specific pattern.

        Tracks whether acting on this pattern improved outcomes.

        Args:
            pattern_id: ID of pattern to check

        Returns:
            Effectiveness metrics if available
        """
        ...

    # ========== Service Status ==========

    @abstractmethod
    async def get_analysis_status(
        self
    ) -> dict:
        """
        Get current analysis status.

        Returns:
            Status including last analysis time, patterns detected, etc.
        """
        ...
