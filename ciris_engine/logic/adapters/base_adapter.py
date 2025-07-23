"""
Base adapter class with common correlation and message handling functionality.
"""
import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from ciris_engine.logic.adapters.base import Service
from ciris_engine.logic import persistence
from ciris_engine.schemas.telemetry.core import (
    ServiceCorrelation, ServiceCorrelationStatus,
    ServiceRequestData, ServiceResponseData, TraceContext
)
from ciris_engine.schemas.runtime.system_context import ChannelContext
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)


class BaseAdapter(Service):
    """
    Base adapter with common correlation functionality.
    
    Provides:
    - Correlation creation for speak/observe actions
    - Message history fetching from correlations
    - Common telemetry patterns
    """
    
    def __init__(
        self,
        adapter_type: str,
        runtime: Any,
        config: Optional[dict] = None
    ) -> None:
        """Initialize base adapter."""
        super().__init__(config)
        self.adapter_type = adapter_type
        self.runtime = runtime
        self._time_service: Optional[TimeServiceProtocol] = None
    
    def _get_time_service(self) -> Optional[TimeServiceProtocol]:
        """Get time service from runtime."""
        if self._time_service is None and self.runtime:
            self._time_service = getattr(self.runtime, 'time_service', None)
        return self._time_service
    
    def get_channel_list(self) -> List[ChannelContext]:
        """
        Get list of available channels for this adapter.
        
        Returns:
            List of ChannelContext objects containing channel information.
        
        This base implementation returns empty list.
        Subclasses should override to provide actual channels.
        """
        return []