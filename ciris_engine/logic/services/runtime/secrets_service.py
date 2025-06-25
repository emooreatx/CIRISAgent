"""
Agent Secrets Tools for CIRIS Agent.

Provides RECALL_SECRET and UPDATE_SECRETS_FILTER tools for encrypted secret
retrieval and filter management with comprehensive audit logging.
"""
import logging
from typing import Dict, List, Literal, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ciris_engine.logic.adapters.tool_registry import ToolRegistry
from pydantic import BaseModel, Field
from ciris_engine.protocols.services import TimeServiceProtocol

from ciris_engine.logic.secrets.service import SecretsService
from ciris_engine.schemas.secrets.core import SecretPattern
from ciris_engine.schemas.services.tools_core import ToolResult, ToolExecutionStatus
from ciris_engine.schemas.runtime.enums import HandlerActionType
from ciris_engine.schemas.services.core.secrets import SecretContext, SecretOperationResult
from pydantic import Field

logger = logging.getLogger(__name__)

class RecallSecretParams(BaseModel):
    """Parameters for RECALL_SECRET tool"""
    secret_uuid: str = Field(description="UUID of the secret to recall")
    purpose: str = Field(description="Why the secret is needed (for audit)")
    decrypt: bool = Field(default=False, description="Whether to decrypt the secret value")

class UpdateSecretsFilterParams(BaseModel):
    """Parameters for UPDATE_SECRETS_FILTER tool"""
    operation: Literal["add_pattern", "remove_pattern", "update_pattern", "get_current", "update_config"]
    
    pattern: Optional[SecretPattern] = None
    
    pattern_name: Optional[str] = None
    
    config_updates: Optional[List[Dict[str, Union[str, bool, List[str]]]]] = None

class SecretsTools:
    """
    Agent secrets tools implementation.
    
    Provides secure access to encrypted secrets and filter management
    with comprehensive audit logging and security controls.
    """
    
    def __init__(self, secrets_service: SecretsService, time_service: TimeServiceProtocol):
        """
        Initialize secrets tools.
        
        Args:
            secrets_service: SecretsService instance for secret operations
            time_service: TimeService for consistent timestamps
        """
        if not time_service:
            raise RuntimeError("CRITICAL: TimeService is required for SecretsTools")
        self.secrets_service = secrets_service
        self._time_service = time_service
        
    async def recall_secret(
        self,
        params: RecallSecretParams,
        requester_id: str = "agent",
        context: Optional[SecretContext] = None
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
        start_time = self._time_service.now()
        
        try:
            secret_record = await self.secrets_service.store.retrieve_secret(params.secret_uuid)
            
            if not secret_record:
                logger.warning(f"Secret not found: {params.secret_uuid}")
                return ToolResult(
                    tool_name="recall_secret",
                    execution_status=ToolExecutionStatus.NOT_FOUND,
                    error_message=f"Secret with UUID {params.secret_uuid} not found",
                    execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
                )
            
            result_data = {
                "secret_uuid": params.secret_uuid,
                "pattern_name": secret_record.detected_pattern,
                "context_hint": secret_record.context_hint,
                "sensitivity": secret_record.sensitivity_level,
                "detected_at": secret_record.created_at.isoformat(),
                "access_count": secret_record.access_count,
                "last_accessed": secret_record.last_accessed.isoformat() if secret_record.last_accessed else None
            }
            
            if params.decrypt:
                try:
                    secret_record = await self.secrets_service.store.get_secret(params.secret_uuid)  # type: ignore[attr-defined]
                    if secret_record:
                        decrypted_value = await self.secrets_service.store.decrypt_secret_value(secret_record)
                        result_data["decrypted_value"] = decrypted_value
                    else:
                        result_data["decrypted_value"] = None
                    
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
                        execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
                    )
            else:
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
                execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000,
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
                execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
            )
    
    async def update_secrets_filter(
        self,
        params: UpdateSecretsFilterParams,
        requester_id: str = "agent",
        context: Optional[SecretContext] = None
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
        start_time = self._time_service.now()
        
        try:
            result_data: Dict[str, Union[str, bool, int, Dict, List, None]] = {"operation": params.operation}
            
            if params.operation == "add_pattern":
                if not params.pattern:
                    return ToolResult(
                        tool_name="update_secrets_filter",
                        execution_status=ToolExecutionStatus.FAILED,
                        error_message="Pattern required for add_pattern operation",
                        execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
                    )
                
                self.secrets_service.filter.add_custom_pattern(params.pattern)
                result_data["pattern_added"] = params.pattern.name
                logger.info(f"Added custom pattern '{params.pattern.name}' by {requester_id}")
                
            elif params.operation == "remove_pattern":
                if not params.pattern_name:
                    return ToolResult(
                        tool_name="update_secrets_filter",
                        execution_status=ToolExecutionStatus.FAILED,
                        error_message="Pattern name required for remove_pattern operation",
                        execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
                    )
                
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
                        execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
                    )
                
                self.secrets_service.filter.remove_custom_pattern(params.pattern.name)
                self.secrets_service.filter.add_custom_pattern(params.pattern)
                result_data["pattern_updated"] = params.pattern.name
                logger.info(f"Updated custom pattern '{params.pattern.name}' by {requester_id}")
                
            elif params.operation == "get_current":
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
                        execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
                    )
                
                success = await self.secrets_service.filter.update_filter_config(params.config_updates)
                
                if success:
                    # Handle the case where config_updates might be a list or dict
                    if isinstance(params.config_updates, dict):
                        result_data["updated_keys"] = list(params.config_updates.keys())
                        logger.info(f"Updated filter config by {requester_id}: {list(params.config_updates.keys())}")
                    elif isinstance(params.config_updates, list):
                        result_data["updated_keys"] = ["list_update"]
                        logger.info(f"Updated filter config by {requester_id}: list of {len(params.config_updates)} items")
                    else:
                        result_data["updated_keys"] = ["unknown"]
                        logger.info(f"Updated filter config by {requester_id}: unknown type")
                else:
                    return ToolResult(
                        tool_name="update_secrets_filter",
                        execution_status=ToolExecutionStatus.FAILED,
                        error_message="Failed to update filter configuration",
                        execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
                    )
                
            else:
                return ToolResult(  # type: ignore[unreachable]
                    tool_name="update_secrets_filter",
                    execution_status=ToolExecutionStatus.FAILED,
                    error_message=f"Unknown operation: {params.operation}",
                    execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
                )
            
            return ToolResult(
                tool_name="update_secrets_filter",
                execution_status=ToolExecutionStatus.SUCCESS,
                result_data=result_data,
                execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000,
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
                execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
            )
    
    async def list_secrets(
        self,
        requester_id: str = "agent",
        include_sensitive: bool = False,
        context: Optional[SecretContext] = None
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
        start_time = self._time_service.now()
        
        try:
            all_secrets = await self.secrets_service.store.list_all_secrets()
            
            secrets_list = []
            for secret in all_secrets:
                secret_info = {
                    "uuid": secret.secret_uuid,  # type: ignore[attr-defined]
                    "pattern_name": secret.detected_pattern,
                    "sensitivity": secret.sensitivity_level,  # type: ignore[attr-defined]
                    "detected_at": secret.created_at.isoformat(),
                    "access_count": secret.access_count,  # type: ignore[attr-defined]
                    "last_accessed": secret.last_accessed.isoformat() if secret.last_accessed else None
                }
                
                if include_sensitive:
                    secret_info["context_hint"] = secret.context_hint
                    secret_info["original_length"] = len(secret.encrypted_value) if secret.encrypted_value else 0  # type: ignore[attr-defined]
                
                secrets_list.append(secret_info)
            
            logger.info(f"Listed {len(secrets_list)} secrets for {requester_id}")
            
            return ToolResult(
                tool_name="list_secrets",
                execution_status=ToolExecutionStatus.SUCCESS,
                result_data={
                    "secrets": secrets_list,
                    "total_count": len(secrets_list),
                    "include_sensitive": include_sensitive
                },
                execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000,
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
                execution_time_ms=(self._time_service.now() - start_time).total_seconds() * 1000
            )

def register_secrets_tools(registry: 'ToolRegistry', secrets_service: SecretsService) -> None:
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