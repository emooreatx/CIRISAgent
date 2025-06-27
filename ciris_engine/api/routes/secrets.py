"""
Secrets service endpoints for CIRIS API v1.

Manages secrets detection, filtering, and audit.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Body
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext
from ciris_engine.schemas.services.core.secrets import (
    SecretsServiceStats,
    SecretFilterStatus,
    SecretAccessLog,
)
from ciris_engine.schemas.secrets.service import (
    FilterUpdateRequest,
    FilterUpdateResult,
    PatternConfig,
    SensitivityConfig,
)
from ciris_engine.schemas.runtime.enums import SensitivityLevel

router = APIRouter(prefix="/secrets", tags=["secrets"])

# Request/Response schemas

class SecretsStats(BaseModel):
    """Secrets service statistics."""
    total_secrets: int = Field(..., description="Total secrets stored")
    active_filters: int = Field(..., description="Number of active filters")
    filter_matches_today: int = Field(..., description="Filter matches today")
    last_filter_update: Optional[datetime] = Field(None, description="Last filter update time")
    encryption_enabled: bool = Field(..., description="Whether encryption is enabled")
    storage_health: bool = Field(..., description="Whether storage is healthy")
    
class FilterList(BaseModel):
    """List of active filters."""
    filters: List[SecretFilterStatus] = Field(..., description="Active filter configurations")
    total: int = Field(..., description="Total filter count")
    
class FilterUpdateResponse(BaseModel):
    """Response for filter update operations."""
    success: bool = Field(..., description="Whether update succeeded")
    message: str = Field(..., description="Result message")
    updated_filters: int = Field(..., description="Number of filters updated")
    error: Optional[str] = Field(None, description="Error details if failed")
    
class SecretTestRequest(BaseModel):
    """Request to test secret detection."""
    content: str = Field(..., description="Content to test for secrets", max_length=10000)
    
class SecretTestResponse(BaseModel):
    """Response from secret detection test."""
    contains_secrets: bool = Field(..., description="Whether secrets were detected")
    patterns_matched: List[str] = Field(..., description="Patterns that matched")
    detected_count: int = Field(..., description="Number of secrets detected")
    
class AuditLogList(BaseModel):
    """List of secret access logs."""
    logs: List[SecretAccessLog] = Field(..., description="Access log entries")
    total: int = Field(..., description="Total log count")
    filtered_count: int = Field(..., description="Number after filtering")

# Endpoints

@router.get("/stats", response_model=SuccessResponse[SecretsStats])
async def get_secrets_stats(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get secrets service statistics.
    
    Returns statistics about stored secrets and filter activity.
    """
    secrets_service = getattr(request.app.state, 'secrets_service', None)
    if not secrets_service:
        raise HTTPException(status_code=503, detail="Secrets service not available")
    
    try:
        # Get service stats
        stats = await secrets_service.get_service_stats()
        
        # Check service health
        is_healthy = await secrets_service.is_healthy()
        
        # Convert to response format
        response_stats = SecretsStats(
            total_secrets=stats.total_secrets,
            active_filters=stats.active_filters,
            filter_matches_today=stats.filter_matches_today,
            last_filter_update=stats.last_filter_update,
            encryption_enabled=stats.encryption_enabled,
            storage_health=is_healthy
        )
        
        return SuccessResponse(data=response_stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filters", response_model=SuccessResponse[FilterList])
async def get_filter_config(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get active filter patterns.
    
    Returns current secret detection filter configuration.
    """
    secrets_service = getattr(request.app.state, 'secrets_service', None)
    if not secrets_service:
        raise HTTPException(status_code=503, detail="Secrets service not available")
    
    try:
        # Get filter configuration
        filter_config = await secrets_service.get_filter_config()
        
        # Convert to response format
        filters = []
        
        # Process patterns if available
        if 'patterns' in filter_config:
            for pattern in filter_config['patterns']:
                filter_status = SecretFilterStatus(
                    filter_name=pattern.get('name', 'unknown'),
                    filter_type='pattern',
                    enabled=pattern.get('enabled', True),
                    pattern_count=1,
                    last_match=None,  # Would need tracking
                    match_count=0,  # Would need tracking
                    metadata={
                        'pattern': pattern.get('pattern', ''),
                        'sensitivity': pattern.get('sensitivity', 'HIGH')
                    }
                )
                filters.append(filter_status)
        
        # Process sensitivity configs if available
        if 'sensitivity_config' in filter_config:
            for level, config in filter_config['sensitivity_config'].items():
                filter_status = SecretFilterStatus(
                    filter_name=f"sensitivity_{level}",
                    filter_type='sensitivity',
                    enabled=config.get('enabled', True),
                    pattern_count=0,
                    last_match=None,
                    match_count=0,
                    metadata={
                        'level': level,
                        'redaction_enabled': str(config.get('redaction_enabled', True)),
                        'audit_enabled': str(config.get('audit_enabled', True))
                    }
                )
                filters.append(filter_status)
        
        filter_list = FilterList(
            filters=filters,
            total=len(filters)
        )
        
        return SuccessResponse(data=filter_list)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/filters", response_model=SuccessResponse[FilterUpdateResponse])
async def update_filters(
    request: Request,
    update_request: FilterUpdateRequest = Body(...),
    auth: AuthContext = Depends(require_admin)
):
    """
    Update filter configuration.
    
    Update secret detection patterns and sensitivity settings. Requires ADMIN role.
    """
    secrets_service = getattr(request.app.state, 'secrets_service', None)
    if not secrets_service:
        raise HTTPException(status_code=503, detail="Secrets service not available")
    
    try:
        # Update filters
        result = await secrets_service.update_filter_config(
            updates=update_request,
            accessor=auth.user_id
        )
        
        # Count updated filters
        updated_count = 0
        if update_request.patterns:
            updated_count += len(update_request.patterns)
        if update_request.sensitivity_config:
            updated_count += len(update_request.sensitivity_config)
        
        # Create response
        response = FilterUpdateResponse(
            success=result.success,
            message="Filters updated successfully" if result.success else "Filter update failed",
            updated_filters=updated_count,
            error=result.error
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test", response_model=SuccessResponse[SecretTestResponse])
async def test_secret_detection(
    request: Request,
    test_request: SecretTestRequest = Body(...),
    auth: AuthContext = Depends(require_observer)
):
    """
    Test secret detection.
    
    Test if content contains secrets without storing them.
    """
    secrets_service = getattr(request.app.state, 'secrets_service', None)
    if not secrets_service:
        raise HTTPException(status_code=503, detail="Secrets service not available")
    
    try:
        # Process text to detect secrets (without storing)
        filtered_text, secret_refs = await secrets_service.process_incoming_text(
            text=test_request.content,
            source_message_id=f"test_{auth.user_id}_{datetime.now(timezone.utc).timestamp()}"
        )
        
        # Extract patterns that matched
        patterns_matched = []
        for ref in secret_refs:
            if ref.detected_pattern not in patterns_matched:
                patterns_matched.append(ref.detected_pattern)
        
        # Create response
        response = SecretTestResponse(
            contains_secrets=len(secret_refs) > 0,
            patterns_matched=patterns_matched,
            detected_count=len(secret_refs)
        )
        
        return SuccessResponse(data=response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit", response_model=SuccessResponse[AuditLogList])
async def get_secrets_audit(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    secret_id: Optional[str] = None,
    operation: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get secrets access audit log.
    
    Returns audit trail of secret access attempts.
    """
    # For now, return empty audit log since we don't have an audit trail implementation
    # In a real implementation, this would query the audit service or secrets service
    # for secret access logs
    
    # Mock implementation
    logs = []
    
    # If we have audit service, we could query it
    audit_service = getattr(request.app.state, 'audit_service', None)
    if audit_service and hasattr(audit_service, 'query_entries'):
        try:
            # Query audit entries related to secrets
            audit_entries = await audit_service.query_entries(
                action_type="secret_access",
                limit=limit,
                offset=offset,
                start_time=start_time,
                end_time=end_time
            )
            
            # Convert to SecretAccessLog format
            for entry in audit_entries:
                if entry.action_type.startswith("secret_"):
                    log = SecretAccessLog(
                        secret_id=entry.parameters.get('secret_id', 'unknown'),
                        operation=entry.action_type,
                        requester_id=entry.user_id or 'system',
                        granted=entry.result.get('success', False),
                        reason=entry.result.get('reason'),
                        context={
                            'operation': entry.action_type,
                            'channel_id': entry.parameters.get('channel_id'),
                            'user_id': entry.user_id,
                            'request_id': entry.request_id,
                            'metadata': {}
                        },
                        timestamp=entry.timestamp
                    )
                    logs.append(log)
        except:
            # If audit service doesn't support this, continue with empty logs
            pass
    
    # Apply filtering
    filtered_logs = logs
    if secret_id:
        filtered_logs = [log for log in filtered_logs if log.secret_id == secret_id]
    if operation:
        filtered_logs = [log for log in filtered_logs if log.operation == operation]
    
    # Create response
    audit_list = AuditLogList(
        logs=filtered_logs[offset:offset + limit],
        total=len(logs),
        filtered_count=len(filtered_logs)
    )
    
    return SuccessResponse(data=audit_list)