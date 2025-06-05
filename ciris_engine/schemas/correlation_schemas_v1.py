from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel

class ServiceCorrelationStatus(str, Enum):
    """Status values for service correlations."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class ServiceCorrelation(BaseModel):
    """Record correlating service requests and responses."""
    correlation_id: ServiceCorrelationStatus
    service_type: ServiceCorrelationStatus
    handler_name: ServiceCorrelationStatus
    action_type: ServiceCorrelationStatus
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    status: ServiceCorrelationStatus = ServiceCorrelationStatus.PENDING
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

__all__ = [
    "ServiceCorrelationStatus",
    "ServiceCorrelation",
]
