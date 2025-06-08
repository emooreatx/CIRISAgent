"""
Agent Secrets Tools for CIRIS Agent.

Provides RECALL_SECRET and UPDATE_SECRETS_FILTER tools for encrypted secret
retrieval and filter management with comprehensive audit logging.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field

from .service import SecretsService
from ..schemas.config_schemas_v1 import SecretPattern
from ..schemas.tool_schemas_v1 import ToolResult, ToolExecutionStatus
from ..schemas.foundational_schemas_v1 import HandlerActionType
from ..schemas.secrets_schemas_v1 import SecretRecord

logger = logging.getLogger(__name__)


class RecallSecretParams(BaseModel):
    """Parameters for RECALL_SECRET tool"""
    secret_uuid: str = Field(description="UUID of the secret to recall")
    purpose: str = Field(description="Why the secret is needed (for audit)")
    decrypt: bool = Field(default=False, description="Whether to decrypt the secret value")


class UpdateSecretsFilterParams(BaseModel):
    """Parameters for UPDATE_SECRETS_FILTER tool"""
    operation: Literal["add_pattern", "remove_pattern", "update_pattern", "get_current", "update_config"]
    
    # For add_pattern/update_pattern
    pattern: Optional[SecretPattern] = None
    
    # For remove_pattern  
    pattern_name: Optional[str] = None
    
    # For configuration changes
    config_updates: Optional[Dict[str, Any]] = None


class SecretsTools:
    """
    Agent secrets tools implementation.
    
    Provides secure access to encrypted secrets and filter management
    with comprehensive audit logging and security controls.
    """
    
    def __init__(self, secrets_service: SecretsService):
        """
        Initialize secrets tools.
        
        Args:
            secrets_service: SecretsService instance for secret operations
        """
        self.secrets_service = secrets_service
        
    async def recall_secret(
        self,
        params: RecallSecretParams,
        requester_id: str = "agent",
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:  # pragma: no cover - integration heavy
        """
        Recall a secret by UUID with optional decryption.
        
        Args:
            params: Tool parameters
            requester_id: ID of the requesting entity
            context: Additional context for audit
            
        Returns:
            ToolResult with secret data or error
        """
        start_time = datetime.now()
        
        try:
            # Retrieve the secret record
            secret_record = await self.secrets_service.store.retrieve_secret(params.secret_uuid)
            
            if not secret_record:
                logger.warning(f"Secret not found: {params.secret_uuid}")
                return ToolResult(
                    tool_name="recall_secret",
                    execution_status=ToolExecutionStatus.NOT_FOUND,
                    error_message=f"Secret with UUID {params.secret_uuid} not found",
                    execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                )
            
            # Prepare result data
            result_data = {
                "secret_uuid": params.secret_uuid,
                "pattern_name": secret_record.detected_pattern,
                "context_hint": secret_record.context_hint,
                "sensitivity": secret_record.sensitivity_level,
                "detected_at": secret_record.created_at.isoformat(),
                "access_count": secret_record.access_count,
                "last_accessed": secret_record.last_accessed.isoformat() if secret_record.last_accessed else None
            }
            
            # Add decrypted value if requested
            if params.decrypt:
                try:
                    decrypted_value = await self.secrets_service.store.decrypt_secret(params.secret_uuid)
                    result_data["decrypted_value"] = decrypted_value
                    
                    # Log access via audit service
                    if hasattr(self.secrets_service, 'audit_service') and self.secrets_service.audit_service:
                        await self.secrets_service.audit_service.log_action(
                            HandlerActionType.TOOL,
                            {
                                "tool_name": "decrypt_secret",
                                "secret_uuid": params.secret_uuid,
                                "requester_id": requester_id,
                                "purpose": params.purpose,
                                "access_type": "decrypt",
                                "granted": True
                            },
                            outcome="success"
                        )
                    
                    logger.info(f"Secret {params.secret_uuid} decrypted for {requester_id}: {params.purpose}")
                    
                except Exception as e:
                    logger.error(f"Failed to decrypt secret {params.secret_uuid}: {e}")
                    
                    # Log failed access via audit service
                    if hasattr(self.secrets_service, 'audit_service') and self.secrets_service.audit_service:
                        await self.secrets_service.audit_service.log_action(
                            HandlerActionType.TOOL,
                            {
                                "tool_name": "decrypt_secret",
                                "secret_uuid": params.secret_uuid,
                                "requester_id": requester_id,
                                "purpose": params.purpose,
                                "access_type": "decrypt",
                                "granted": False,
                                "error": str(e)
                            },
                            outcome="failed"
                        )
                    
                    return ToolResult(
                        tool_name="recall_secret",
                        execution_status=ToolExecutionStatus.FAILED,
                        error_message=f"Failed to decrypt secret: {str(e)}",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                    )
            else:
                # Log metadata access via audit service
                if hasattr(self.secrets_service, 'audit_service') and self.secrets_service.audit_service:
                    await self.secrets_service.audit_service.log_action(
                        HandlerActionType.TOOL,
                        {
                            "tool_name": "recall_secret",
                            "secret_uuid": params.secret_uuid,
                            "requester_id": requester_id,
                            "purpose": params.purpose,
                            "access_type": "metadata",
                            "granted": True
                        },
                        outcome="success"
                )
                
                logger.info(f"Secret {params.secret_uuid} metadata accessed by {requester_id}: {params.purpose}")
            
            return ToolResult(
                tool_name="recall_secret",
                execution_status=ToolExecutionStatus.SUCCESS,
                result_data=result_data,
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                metadata={
                    "decrypted": params.decrypt,
                    "purpose": params.purpose,
                    "requester_id": requester_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error in recall_secret: {e}")
            return ToolResult(
                tool_name="recall_secret",
                execution_status=ToolExecutionStatus.FAILED,
                error_message=f"Internal error: {str(e)}",
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )
    
    async def update_secrets_filter(
        self,
        params: UpdateSecretsFilterParams,
        requester_id: str = "agent",
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:  # pragma: no cover - integration heavy
        """
        Update secrets filter configuration or patterns.
        
        Args:
            params: Tool parameters
            requester_id: ID of the requesting entity
            context: Additional context for audit
            
        Returns:
            ToolResult with operation result
        """
        start_time = datetime.now()
        
        try:
            result_data = {"operation": params.operation}
            
            if params.operation == "add_pattern":
                if not params.pattern:
                    return ToolResult(
                        tool_name="update_secrets_filter",
                        execution_status=ToolExecutionStatus.FAILED,
                        error_message="Pattern required for add_pattern operation",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                    )
                
                # Add pattern to filter
                self.secrets_service.filter.add_custom_pattern(params.pattern)
                result_data["pattern_added"] = params.pattern.name
                logger.info(f"Added custom pattern '{params.pattern.name}' by {requester_id}")
                
            elif params.operation == "remove_pattern":
                if not params.pattern_name:
                    return ToolResult(
                        tool_name="update_secrets_filter",
                        execution_status=ToolExecutionStatus.FAILED,
                        error_message="Pattern name required for remove_pattern operation",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                    )
                
                # Remove pattern from filter
                removed = self.secrets_service.filter.remove_custom_pattern(params.pattern_name)
                if removed:
                    result_data["pattern_removed"] = params.pattern_name
                    logger.info(f"Removed custom pattern '{params.pattern_name}' by {requester_id}")
                else:
                    result_data["pattern_removed"] = None
                    result_data["message"] = f"Pattern '{params.pattern_name}' not found"
                
            elif params.operation == "update_pattern":
                if not params.pattern:
                    return ToolResult(
                        tool_name="update_secrets_filter",
                        execution_status=ToolExecutionStatus.FAILED,
                        error_message="Pattern required for update_pattern operation",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                    )
                
                # Update existing pattern (remove and re-add)
                self.secrets_service.filter.remove_custom_pattern(params.pattern.name)
                self.secrets_service.filter.add_custom_pattern(params.pattern)
                result_data["pattern_updated"] = params.pattern.name
                logger.info(f"Updated custom pattern '{params.pattern.name}' by {requester_id}")
                
            elif params.operation == "get_current":
                # Get current filter configuration
                config = self.secrets_service.filter.export_config()
                stats = self.secrets_service.filter.get_pattern_stats()
                
                result_data["config"] = config
                result_data["stats"] = stats
                
            elif params.operation == "update_config":
                if not params.config_updates:
                    return ToolResult(
                        tool_name="update_secrets_filter",
                        execution_status=ToolExecutionStatus.FAILED,
                        error_message="Config updates required for update_config operation",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                    )
                
                # Update filter configuration
                success = await self.secrets_service.filter.update_filter_config(params.config_updates)
                
                if success:
                    result_data["updated_keys"] = list(params.config_updates.keys())
                    logger.info(f"Updated filter config by {requester_id}: {list(params.config_updates.keys())}")
                else:
                    return ToolResult(
                        tool_name="update_secrets_filter",
                        execution_status=ToolExecutionStatus.FAILED,
                        error_message="Failed to update filter configuration",
                        execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                    )
                
            else:
                return ToolResult(
                    tool_name="update_secrets_filter",
                    execution_status=ToolExecutionStatus.FAILED,
                    error_message=f"Unknown operation: {params.operation}",
                    execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                )
            
            return ToolResult(
                tool_name="update_secrets_filter",
                execution_status=ToolExecutionStatus.SUCCESS,
                result_data=result_data,
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                metadata={
                    "operation": params.operation,
                    "requester_id": requester_id
                }
            )
            
        except Exception as e:
            logger.error(f"Error in update_secrets_filter: {e}")
            return ToolResult(
                tool_name="update_secrets_filter",
                execution_status=ToolExecutionStatus.FAILED,
                error_message=f"Internal error: {str(e)}",
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )
    
    async def list_secrets(
        self,
        requester_id: str = "agent",
        include_sensitive: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:  # pragma: no cover - integration heavy
        """
        List all stored secrets (metadata only).
        
        Args:
            requester_id: ID of the requesting entity
            include_sensitive: Whether to include sensitive metadata
            context: Additional context for audit
            
        Returns:
            ToolResult with secrets list
        """
        start_time = datetime.now()
        
        try:
            # Get all secret records
            all_secrets = await self.secrets_service.store.list_all_secrets()
            
            secrets_list = []
            for secret in all_secrets:
                secret_info = {
                    "uuid": secret.secret_uuid,
                    "pattern_name": secret.detected_pattern,
                    "sensitivity": secret.sensitivity_level,
                    "detected_at": secret.created_at.isoformat(),
                    "access_count": secret.access_count,
                    "last_accessed": secret.last_accessed.isoformat() if secret.last_accessed else None
                }
                
                if include_sensitive:
                    secret_info["context_hint"] = secret.context_hint
                    secret_info["original_length"] = len(secret.encrypted_value) if secret.encrypted_value else 0
                
                secrets_list.append(secret_info)
            
            # Log the listing access
            logger.info(f"Listed {len(secrets_list)} secrets for {requester_id}")
            
            return ToolResult(
                tool_name="list_secrets",
                execution_status=ToolExecutionStatus.SUCCESS,
                result_data={
                    "secrets": secrets_list,
                    "total_count": len(secrets_list),
                    "include_sensitive": include_sensitive
                },
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                metadata={
                    "requester_id": requester_id,
                    "include_sensitive": include_sensitive
                }
            )
            
        except Exception as e:
            logger.error(f"Error in list_secrets: {e}")
            return ToolResult(
                tool_name="list_secrets",
                execution_status=ToolExecutionStatus.FAILED,
                error_message=f"Internal error: {str(e)}",
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )


def register_secrets_tools(registry: Any, secrets_service: SecretsService) -> None:
    """Register secrets tools in the ToolRegistry."""
    secrets_tools = SecretsTools(secrets_service)
    
    registry.register_tool(
        "recall_secret",
        schema={
            "secret_uuid": str,
            "purpose": str,
            "decrypt": bool
        },
        handler=lambda args: secrets_tools.recall_secret(
            RecallSecretParams(**args)
        ),
    )
    
    registry.register_tool(
        "update_secrets_filter",
        schema={
            "operation": str,
            "pattern": (dict, type(None)),
            "pattern_name": (str, type(None)),
            "config_updates": (dict, type(None))
        },
        handler=lambda args: secrets_tools.update_secrets_filter(
            UpdateSecretsFilterParams(**args)
        ),
    )
    
    registry.register_tool(
        "list_secrets",
        schema={
            "include_sensitive": bool
        },
        handler=lambda args: secrets_tools.list_secrets(
            include_sensitive=args.get("include_sensitive", False)
        ),
    )