"""
Config service endpoints for CIRIS API v1.

Graph-based configuration management.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends, Path
from pydantic import BaseModel, Field, field_serializer

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.api.config_security import filter_config_for_role
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

router = APIRouter(prefix="/config", tags=["config"])

# Request/Response schemas

class ConfigItemResponse(BaseModel):
    """Configuration item in API response."""
    key: str = Field(..., description="Configuration key")
    value: Any = Field(..., description="Configuration value")
    updated_at: datetime = Field(..., description="Last update time")
    updated_by: str = Field(..., description="Who updated this config")
    is_sensitive: bool = Field(False, description="Whether value contains sensitive data")
    
    @field_serializer('updated_at')
    def serialize_updated_at(self, updated_at: datetime, _info):
        return updated_at.isoformat() if updated_at else None

class ConfigListResponse(BaseModel):
    """List of configuration values."""
    configs: List[ConfigItemResponse] = Field(..., description="Configuration entries")
    total: int = Field(..., description="Total count")

class ConfigUpdate(BaseModel):
    """Configuration update request."""
    value: Any = Field(..., description="New configuration value")
    reason: Optional[str] = Field(None, description="Reason for change")

class ConfigHistory(BaseModel):
    """Configuration change history."""
    key: str = Field(..., description="Configuration key")
    changes: List[Dict[str, Any]] = Field(..., description="Historical changes")

class ConfigValidation(BaseModel):
    """Configuration validation request."""
    configs: Dict[str, Any] = Field(..., description="Configurations to validate")

class ConfigValidationResult(BaseModel):
    """Configuration validation result."""
    valid: bool = Field(..., description="Whether all configs are valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")

# Endpoints

@router.get("/values", response_model=SuccessResponse[ConfigListResponse])
async def list_configs(
    request: Request,
    prefix: Optional[str] = None,
    auth: AuthContext = Depends(require_observer)
):
    """
    List all configurations.
    
    Get all configuration values, with sensitive values filtered based on role.
    """
    config_service = getattr(request.app.state, 'config_service', None)
    if not config_service:
        raise HTTPException(status_code=503, detail="Config service not available")
    
    try:
        # Get all configs
        all_configs = {}
        if hasattr(config_service, 'get_all_configs'):
            all_configs = await config_service.get_all_configs()
        elif hasattr(config_service, 'get_config'):
            # Try to get essential config
            essential_config = await config_service.get_config()
            if essential_config:
                all_configs = essential_config
        
        # Filter based on prefix if provided
        if prefix:
            all_configs = {k: v for k, v in all_configs.items() if k.startswith(prefix)}
        
        # Apply role-based filtering
        filtered_configs = filter_config_for_role(all_configs, auth.role)
        
        # Convert to list format
        config_list = []
        for key, value in filtered_configs.items():
            is_sensitive = value == "[REDACTED]"
            config_list.append(ConfigItemResponse(
                key=key,
                value=value,
                updated_at=datetime.now(timezone.utc),  # Would get from graph
                updated_by="system",  # Would get from graph
                is_sensitive=is_sensitive
            ))
        
        result = ConfigListResponse(
            configs=config_list,
            total=len(config_list)
        )
        
        return SuccessResponse(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/values/{key:path}", response_model=SuccessResponse[ConfigItemResponse])
async def get_config(
    request: Request,
    key: str = Path(..., description="Configuration key"),
    auth: AuthContext = Depends(require_observer)
):
    """
    Get specific config.
    
    Get a specific configuration value.
    """
    config_service = getattr(request.app.state, 'config_service', None)
    if not config_service:
        raise HTTPException(status_code=503, detail="Config service not available")
    
    try:
        # Get config value
        value = await config_service.get_config(key)
        
        if value is None:
            raise HTTPException(status_code=404, detail=f"Configuration key '{key}' not found")
        
        # Apply role-based filtering
        filtered = filter_config_for_role({key: value}, auth.role)
        filtered_value = filtered.get(key, "[REDACTED]")
        
        config = ConfigItemResponse(
            key=key,
            value=filtered_value,
            updated_at=datetime.now(timezone.utc),
            updated_by="system",
            is_sensitive=filtered_value == "[REDACTED]"
        )
        
        return SuccessResponse(data=config)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/values/{key:path}", response_model=SuccessResponse[ConfigItemResponse])
async def update_config(
    request: Request,
    body: ConfigUpdate,
    key: str = Path(..., description="Configuration key"),
    auth: AuthContext = Depends(require_admin)
):
    """
    Update config.
    
    Update a configuration value. Requires ADMIN role.
    """
    config_service = getattr(request.app.state, 'config_service', None)
    if not config_service:
        raise HTTPException(status_code=503, detail="Config service not available")
    
    try:
        # Update config
        await config_service.set_config(
            key=key,
            value=body.value,
            updated_by=auth.user_id
        )
        
        # Return updated config
        config = ConfigItemResponse(
            key=key,
            value=body.value,
            updated_at=datetime.now(timezone.utc),
            updated_by=auth.user_id,
            is_sensitive=False
        )
        
        return SuccessResponse(data=config)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/values/{key:path}", response_model=SuccessResponse[Dict[str, str]])
async def delete_config(
    request: Request,
    key: str = Path(..., description="Configuration key"),
    auth: AuthContext = Depends(require_admin)
):
    """
    Delete config.
    
    Remove a configuration value. Requires ADMIN role.
    """
    config_service = getattr(request.app.state, 'config_service', None)
    if not config_service:
        raise HTTPException(status_code=503, detail="Config service not available")
    
    try:
        # Delete config
        if hasattr(config_service, 'delete_config'):
            await config_service.delete_config(key)
        else:
            # Set to None as deletion
            await config_service.set_config(key, None, updated_by=auth.user_id)
        
        return SuccessResponse(data={"status": "deleted", "key": key})
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{key:path}", response_model=SuccessResponse[ConfigHistory])
async def get_config_history(
    request: Request,
    key: str = Path(..., description="Configuration key"),
    limit: int = 50,
    auth: AuthContext = Depends(require_observer)
):
    """
    Configuration history.
    
    Get change history for a configuration key.
    """
    config_service = getattr(request.app.state, 'config_service', None)
    if not config_service:
        raise HTTPException(status_code=503, detail="Config service not available")
    
    try:
        # Get history from audit trail
        changes = []
        
        # Check if config service has history method
        if hasattr(config_service, 'get_config_history'):
            history_entries = await config_service.get_config_history(key, limit)
            
            for entry in history_entries:
                change = {
                    "timestamp": entry.get('timestamp', datetime.now(timezone.utc)),
                    "value": entry.get('value'),
                    "updated_by": entry.get('updated_by', 'unknown'),
                    "reason": entry.get('reason')
                }
                
                # Apply role-based filtering to historical values
                if auth.role.value < 2:  # Below ADMIN
                    filtered = filter_config_for_role({key: change['value']}, auth.role)
                    change['value'] = filtered.get(key, "[REDACTED]")
                
                # Convert datetime to ISO format
                if isinstance(change.get('timestamp'), datetime):
                    change['timestamp'] = change['timestamp'].isoformat()
                
                changes.append(change)
        
        history = ConfigHistory(
            key=key,
            changes=changes
        )
        
        return SuccessResponse(data=history)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate", response_model=SuccessResponse[ConfigValidationResult])
async def validate_config(
    request: Request,
    body: ConfigValidation,
    auth: AuthContext = Depends(require_admin)
):
    """
    Validate config changes.
    
    Check if configuration changes are valid without applying them.
    """
    config_service = getattr(request.app.state, 'config_service', None)
    if not config_service:
        raise HTTPException(status_code=503, detail="Config service not available")
    
    try:
        errors = []
        warnings = []
        
        # Validate each config
        for key, value in body.configs.items():
            # Check for dangerous configs
            if key.startswith("system.") and auth.role != "ROOT":
                errors.append(f"Cannot modify system config '{key}' without ROOT role")
            
            # Check for sensitive configs
            sensitive_patterns = ["key", "secret", "token", "password"]
            if any(pattern in key.lower() for pattern in sensitive_patterns):
                warnings.append(f"Config '{key}' appears to contain sensitive data")
            
            # Type validation
            if value is None:
                warnings.append(f"Config '{key}' is being set to null")
        
        result = ConfigValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
        
        return SuccessResponse(data=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))