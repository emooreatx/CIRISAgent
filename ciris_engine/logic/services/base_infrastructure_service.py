"""
Base Infrastructure Service - Extends BaseService for system-level services.
"""
from typing import Dict, Any

from ciris_engine.logic.services.base_service import BaseService
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.services.metadata import ServiceMetadata
from ciris_engine.schemas.services.core import ServiceCapabilities


class BaseInfrastructureService(BaseService):
    """
    Base class for infrastructure services.
    
    Infrastructure services are critical system-level services that:
    - Provide core functionality (time, auth, resource monitoring)
    - Have high availability requirements
    - Are marked as critical in metadata
    
    Subclasses should override get_service_type() to return the
    appropriate ServiceType enum value.
    """
    
    def get_service_type(self) -> ServiceType:
        """Infrastructure services can be various types.
        
        Subclasses should override to return specific type like:
        - ServiceType.TIME for time services
        - ServiceType.SHUTDOWN for shutdown services
        - ServiceType.INITIALIZATION for init services
        - ServiceType.VISIBILITY for visibility services
        
        Default returns TIME as a common infrastructure type.
        """
        return ServiceType.TIME
    
    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities with infrastructure metadata."""
        # Get metadata dict from parent's _get_metadata()
        service_metadata = self._get_metadata()
        metadata_dict = service_metadata.model_dump() if isinstance(service_metadata, ServiceMetadata) else {}
        
        # Add infrastructure-specific metadata
        metadata_dict.update({
            "category": "infrastructure",
            "critical": True
        })
        
        return ServiceCapabilities(
            service_name=self.service_name,
            actions=self._get_actions(),
            version=self._version,
            dependencies=list(self._dependencies),
            metadata=metadata_dict
        )
    
    def _get_metadata(self) -> ServiceMetadata:
        """
        Get infrastructure service metadata.
        
        Returns ServiceMetadata for type safety.
        Subclasses can override to add more specific metadata.
        """
        # Return base metadata - infrastructure-specific attributes
        # are now handled through other mechanisms
        return super()._get_metadata()
    
    def _collect_custom_metrics(self) -> Dict[str, float]:
        """
        Collect infrastructure-specific metrics.
        
        Adds availability metric based on uptime.
        """
        metrics = super()._collect_custom_metrics()
        
        # Calculate availability (simplified - just based on uptime)
        uptime = self._calculate_uptime()
        if uptime > 0:
            # Simple availability: 1.0 if up for more than 60 seconds
            availability = min(1.0, uptime / 60.0)
        else:
            availability = 0.0
            
        metrics.update({
            "availability": availability
        })
        
        return metrics