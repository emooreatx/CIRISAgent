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
    ServiceRequestData, ServiceResponseData
)
from ciris_engine.schemas.runtime.messages import FetchedMessage
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
    
    async def create_speak_correlation(
        self,
        channel_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a correlation for outgoing 'speak' action."""
        correlation_id = str(uuid.uuid4())
        time_service = self._get_time_service()
        now = time_service.now() if time_service else datetime.now(timezone.utc)
        
        # Build parameters
        parameters = {
            "content": content,
            "channel_id": channel_id
        }
        if metadata:
            parameters.update(metadata)
        
        correlation = ServiceCorrelation(
            correlation_id=correlation_id,
            trace_id=str(uuid.uuid4()),  # Required field
            parent_span_id=None,  # Required field
            span_id=str(uuid.uuid4()),  # Required field
            service_type=self.adapter_type,
            handler_name=f"{self.adapter_type.title()}Adapter",
            action_type="speak",
            channel_id=channel_id,  # Required field
            request_data=ServiceRequestData(
                service_type=self.adapter_type,
                method_name="speak",
                channel_id=channel_id,
                parameters=parameters,
                request_timestamp=now
            ),
            response_data=ServiceResponseData(
                service_type=self.adapter_type,  # Required field
                method_name="speak",  # Required field
                success=True,
                result_summary="Message sent",
                execution_time_ms=0,
                response_timestamp=now
            ),
            status=ServiceCorrelationStatus.COMPLETED,
            created_at=now,
            updated_at=now,
            timestamp=now
        )
        
        persistence.add_correlation(correlation)
        logger.debug(f"Created speak correlation {correlation_id} for channel {channel_id}")
        return correlation_id
    
    async def create_observe_correlation(
        self,
        channel_id: str,
        message_id: str,
        content: str,
        author_id: str,
        author_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a correlation for incoming 'observe' action."""
        correlation_id = str(uuid.uuid4())
        time_service = self._get_time_service()
        now = time_service.now() if time_service else datetime.now(timezone.utc)
        
        # Build parameters
        parameters = {
            "content": content,
            "channel_id": channel_id,
            "message_id": message_id,
            "author_id": author_id,
            "author_name": author_name
        }
        if metadata:
            parameters.update(metadata)
        
        correlation = ServiceCorrelation(
            correlation_id=correlation_id,
            trace_id=str(uuid.uuid4()),  # Required field
            parent_span_id=None,  # Required field
            span_id=str(uuid.uuid4()),  # Required field
            service_type=self.adapter_type,
            handler_name=f"{self.adapter_type.title()}Adapter",
            action_type="observe",
            channel_id=channel_id,  # Required field
            request_data=ServiceRequestData(
                service_type=self.adapter_type,
                method_name="observe",
                channel_id=channel_id,
                parameters=parameters,
                request_timestamp=now
            ),
            response_data=ServiceResponseData(
                service_type=self.adapter_type,  # Required field
                method_name="observe",  # Required field
                success=True,
                result_summary="Message observed",
                execution_time_ms=0,
                response_timestamp=now
            ),
            status=ServiceCorrelationStatus.COMPLETED,
            created_at=now,
            updated_at=now,
            timestamp=now
        )
        
        persistence.add_correlation(correlation)
        logger.debug(f"Created observe correlation {correlation_id} for message {message_id}")
        return correlation_id
    
    async def fetch_messages_from_correlations(
        self,
        channel_id: str,
        limit: int = 50,
        before: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch messages from correlations database.
        
        Returns messages in a common format that adapters can transform.
        """
        from ciris_engine.logic.persistence import get_correlations_by_channel
        
        try:
            # Get correlations for this channel
            correlations = get_correlations_by_channel(
                channel_id=channel_id,
                limit=limit,
                before=before
            )
            
            messages = []
            for corr in correlations:
                # Extract message data from correlation
                if corr.action_type == "speak" and corr.request_data:
                    # Outgoing message from agent
                    content = ""
                    if hasattr(corr.request_data, 'parameters') and corr.request_data.parameters:
                        content = corr.request_data.parameters.get("content", "")
                    
                    messages.append({
                        "message_id": corr.correlation_id,
                        "author_id": "ciris",
                        "author_name": "CIRIS",
                        "content": content,
                        "timestamp": corr.timestamp or corr.created_at,
                        "channel_id": channel_id,
                        "is_agent_message": True,
                        "correlation": corr  # Include full correlation for adapter-specific processing
                    })
                    
                elif corr.action_type == "observe" and corr.request_data:
                    # Incoming message from user
                    content = ""
                    author_id = "unknown"
                    author_name = "User"
                    
                    if hasattr(corr.request_data, 'parameters') and corr.request_data.parameters:
                        params = corr.request_data.parameters
                        content = params.get("content", "")
                        author_id = params.get("author_id", "unknown")
                        author_name = params.get("author_name", "User")
                    
                    messages.append({
                        "message_id": corr.correlation_id,
                        "author_id": author_id,
                        "author_name": author_name,
                        "content": content,
                        "timestamp": corr.timestamp or corr.created_at,
                        "channel_id": channel_id,
                        "is_agent_message": False,
                        "correlation": corr
                    })
            
            # Sort by timestamp
            messages.sort(key=lambda m: m["timestamp"] if isinstance(m["timestamp"], datetime) else datetime.fromisoformat(str(m["timestamp"])))
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to fetch messages from correlations for channel {channel_id}: {e}")
            return []
    
    async def get_conversation_context(
        self,
        channel_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get conversation context from correlations for passive observations.
        
        This replaces the in-memory _history approach with correlation-based history.
        """
        messages = await self.fetch_messages_from_correlations(channel_id, limit=limit)
        
        # Format for context (similar to what BaseObserver expects)
        context = []
        for msg in messages:
            context.append({
                "author": msg["author_name"],
                "author_id": msg["author_id"],
                "content": msg["content"],
                "timestamp": msg["timestamp"],
                "is_agent": msg["is_agent_message"]
            })
        
        return context
    
    def get_channel_list(self) -> List[Dict[str, Any]]:
        """
        Get list of available channels for this adapter.
        
        Returns:
            List of channel information dicts with at least:
            - channel_id: str
            - channel_name: Optional[str]
            - channel_type: str (adapter type)
            - is_active: bool
            - last_activity: Optional[datetime]
        
        This base implementation returns empty list.
        Subclasses should override to provide actual channels.
        """
        return []