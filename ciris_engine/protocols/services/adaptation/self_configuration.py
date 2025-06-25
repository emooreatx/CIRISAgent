"""
Protocol for Self-Configuration Service - Orchestrating continuous adaptation.

This service enables autonomous improvement within identity bounds through
observability correlation, pattern learning, and controlled adaptation.
"""

from typing import List, Optional, Protocol, TYPE_CHECKING
from datetime import timedelta
from abc import abstractmethod

from ...runtime.base import ServiceProtocol

# Import forward references for schemas
if TYPE_CHECKING:
    from ciris_engine.schemas.services.special.self_configuration import (
        AgentIdentityRoot,
        AdaptationStatus,
        AdaptationCycleResult,
        ReviewOutcome,
        ServiceImprovementReport,
        ObservabilityAnalysis,
        AdaptationEffectiveness,
        PatternLibrarySummary,
        SystemSnapshot
    )

class SelfConfigurationServiceProtocol(ServiceProtocol, Protocol):
    """
    Protocol for self-configuration service.
    
    Orchestrates continuous adaptation through:
    - Unified observability analysis
    - Pattern-based learning
    - Variance-bounded changes
    - Impact measurement
    - Knowledge accumulation
    """
    
    # ========== Initialization ==========
    
    @abstractmethod
    async def initialize_baseline(
        self, 
        identity: "AgentIdentityRoot"
    ) -> str:
        """
        Establish identity baseline for variance monitoring.
        
        Must be called once during agent initialization to set the
        reference point for all future variance calculations.
        
        Args:
            identity: The agent's root identity configuration
            
        Returns:
            Baseline ID for future reference
        """
        ...
    
    
    # ========== Observability Analysis ==========
    
    @abstractmethod
    async def analyze_observability_window(
        self,
        window: timedelta = timedelta(hours=6)
    ) -> "ObservabilityAnalysis":
        """
        Analyze all observability signals for adaptation opportunities.
        
        Correlates data from:
        - Visibility (traces)
        - Audit (logs)
        - Telemetry (metrics/TSDB)
        - Incidents (errors)
        - Security (threats)
        
        Args:
            window: Time window to analyze
            
        Returns:
            Comprehensive analysis with adaptation opportunities
        """
        ...
    
    # ========== Adaptation Lifecycle ==========
    
    @abstractmethod
    async def get_adaptation_status(self) -> "AdaptationStatus":
        """
        Get current adaptation cycle status and metrics.
        
        Returns:
            Complete status including state, variance, history
        """
        ...
    
    @abstractmethod
    async def trigger_adaptation_cycle(self) -> "AdaptationCycleResult":
        """
        Manually trigger an adaptation assessment cycle.
        
        Useful for testing or urgent adaptation needs.
        Subject to all safety constraints.
        
        Returns:
            Results of the adaptation cycle
        """
        ...
    
    # ========== Change Management ==========
    
    @abstractmethod
    async def get_pending_changes(self) -> List["ConfigurationChange"]:
        """
        Get proposed configuration changes awaiting application.
        
        Returns:
            List of changes with estimated variance impact
        """
        ...
    
    @abstractmethod
    async def approve_changes(
        self, 
        change_ids: List[str],
        approver: str = "system"
    ) -> "ChangeApprovalResult":
        """
        Approve specific configuration changes for application.
        
        Args:
            change_ids: IDs of changes to approve
            approver: Who approved (system or WA ID)
            
        Returns:
            Result of approval including applied changes
        """
        ...
    
    # ========== Pattern Learning ==========
    
    @abstractmethod
    async def get_pattern_library(self) -> "PatternLibrarySummary":
        """
        Get summary of learned adaptation patterns.
        
        Returns:
            Library summary with successful patterns
        """
        ...
    
    @abstractmethod
    async def measure_adaptation_effectiveness(
        self,
        adaptation_id: str
    ) -> "AdaptationEffectiveness":
        """
        Measure if an adaptation actually improved the system.
        
        Analyzes impact across all observability dimensions.
        
        Args:
            adaptation_id: ID of adaptation to measure
            
        Returns:
            Effectiveness metrics across all signals
        """
        ...
    
    # ========== Control Operations ==========
    
    @abstractmethod
    async def resume_after_review(
        self,
        review_outcome: "ReviewOutcome"
    ) -> None:
        """
        Resume adaptation after WA review completion.
        
        Called when variance exceeded threshold and WA
        has completed review of proposed changes.
        
        Args:
            review_outcome: WA's decision and feedback
        """
        ...
    
    @abstractmethod
    async def emergency_stop(
        self, 
        reason: str
    ) -> None:
        """
        Emergency stop all adaptation activities.
        
        Prevents any further adaptations until manually reset.
        Use only in critical situations.
        
        Args:
            reason: Why emergency stop was triggered
        """
        ...
    
    # ========== Reporting ==========
    
    @abstractmethod
    async def get_improvement_report(
        self,
        period: timedelta = timedelta(days=30)
    ) -> "ServiceImprovementReport":
        """
        Generate service improvement report for period.
        
        Summarizes all adaptations, their impacts, and
        overall system improvement metrics.
        
        Args:
            period: Time period to report on
            
        Returns:
            Comprehensive improvement report
        """
        ...