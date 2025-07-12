"""
Secrets Tool Service - Provides secrets management tools.

Implements ToolService protocol to expose RECALL_SECRET and UPDATE_SECRETS_FILTER tools.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from ciris_engine.protocols.services import ToolService
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.adapters.tools import (
    ToolInfo, ToolParameterSchema, ToolExecutionResult,
    ToolResult, ToolExecutionStatus
)
from ciris_engine.logic.secrets.service import SecretsService
from ciris_engine.schemas.services.core.secrets import SecretContext
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus

logger = logging.getLogger(__name__)


class SecretsToolService(ToolService):
    """Service providing secrets management tools."""

    def __init__(self, secrets_service: SecretsService, time_service: TimeServiceProtocol) -> None:
        """Initialize with secrets service and time service."""
        self.secrets_service = secrets_service
        self.time_service = time_service
        self.adapter_name = "secrets"
        self._start_time: Optional[datetime] = None

    async def start(self) -> None:
        """Start the service."""
        self._start_time = self.time_service.now()
        logger.info("SecretsToolService started")

    async def stop(self) -> None:
        """Stop the service."""
        logger.info("SecretsToolService stopped")

    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return True

    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolExecutionResult:
        """Execute a tool and return the result."""
        if tool_name == "recall_secret":
            result = await self._recall_secret(parameters)
        elif tool_name == "update_secrets_filter":
            result = await self._update_secrets_filter(parameters)
        elif tool_name == "self_help":
            result = await self._self_help(parameters)
        else:
            result = ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}"
            )

        return ToolExecutionResult(
            tool_name=tool_name,
            status=ToolExecutionStatus.COMPLETED if result.success else ToolExecutionStatus.FAILED,
            success=result.success,
            data=result.data,
            error=result.error,
            correlation_id=f"secrets_{tool_name}_{datetime.now().timestamp()}"
        )

    async def _recall_secret(self, params: dict) -> ToolResult:
        """Recall a secret by UUID."""
        try:
            secret_uuid = params.get('secret_uuid')
            purpose = params.get('purpose', 'No purpose specified')
            decrypt = params.get('decrypt', False)

            if not secret_uuid:
                return ToolResult(success=False, error="secret_uuid is required")

            # Create context for audit
            context = SecretContext(
                operation="recall",
                request_id=f"recall_{secret_uuid}_{self.time_service.now().timestamp()}",
                metadata={"purpose": purpose}
            )

            # Retrieve the secret
            if decrypt:
                value = self.secrets_service.retrieve(secret_uuid, context)
                if value is None:
                    return ToolResult(success=False, error=f"Secret {secret_uuid} not found")
                result_data = {"value": value, "decrypted": True}
            else:
                # Just verify it exists
                secret = self.secrets_service.store.get_secret(secret_uuid)
                if secret is None:
                    return ToolResult(success=False, error=f"Secret {secret_uuid} not found")
                result_data = {
                    "exists": True,
                    "pattern": secret.pattern.value,
                    "decrypted": False
                }

            return ToolResult(
                success=True,
                data=result_data
            )

        except Exception as e:
            logger.error(f"Error recalling secret: {e}")
            return ToolResult(success=False, error=str(e))

    async def _update_secrets_filter(self, params: dict) -> ToolResult:
        """Update secrets filter configuration."""
        try:
            operation = params.get('operation')
            if not operation:
                return ToolResult(success=False, error="operation is required")

            result_data = {"operation": operation}

            if operation == "add_pattern":
                pattern = params.get('pattern')
                pattern_type = params.get('pattern_type', 'regex')
                if not pattern:
                    return ToolResult(success=False, error="pattern is required for add_pattern")

                self.secrets_service.filter.add_pattern(pattern, pattern_type)
                result_data.update({"pattern": pattern, "pattern_type": pattern_type})

            elif operation == "remove_pattern":
                pattern = params.get('pattern')
                if not pattern:
                    return ToolResult(success=False, error="pattern is required for remove_pattern")

                self.secrets_service.filter.remove_pattern(pattern)
                result_data.update({"pattern": pattern})

            elif operation == "list_patterns":
                patterns = self.secrets_service.filter.list_patterns()
                result_data.update({"patterns": patterns})

            elif operation == "enable":
                enabled = params.get('enabled', True)
                self.secrets_service.filter.enabled = enabled
                result_data.update({"enabled": enabled})

            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")

            return ToolResult(success=True, data=result_data)

        except Exception as e:
            logger.error(f"Error updating secrets filter: {e}")
            return ToolResult(success=False, error=str(e))

    async def _self_help(self, parameters: dict) -> ToolResult:
        """Access the agent experience document."""
        try:
            experience_path = Path("docs/agent_experience.md")

            if not experience_path.exists():
                return ToolResult(
                    success=False,
                    error="Agent experience document not found at docs/agent_experience.md"
                )

            content = experience_path.read_text()

            return ToolResult(
                success=True,
                data={
                    "content": content,
                    "source": "docs/agent_experience.md",
                    "length": len(content)
                }
            )

        except Exception as e:
            logger.error(f"Error reading experience document: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return ["recall_secret", "update_secrets_filter", "self_help"]

    async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """Get detailed information about a specific tool."""
        if tool_name == "recall_secret":
            return ToolInfo(
                name="recall_secret",
                description="Recall a stored secret by UUID",
                parameters=ToolParameterSchema(
                    type="object",
                    properties={
                        "secret_uuid": {"type": "string", "description": "UUID of the secret to recall"},
                        "purpose": {"type": "string", "description": "Why the secret is needed (for audit)"},
                        "decrypt": {"type": "boolean", "description": "Whether to decrypt the secret value", "default": False}
                    },
                    required=["secret_uuid", "purpose"]
                ),
                category="security",
                when_to_use="When you need to retrieve a previously stored secret value"
            )
        elif tool_name == "update_secrets_filter":
            return ToolInfo(
                name="update_secrets_filter",
                description="Update secrets detection filter configuration",
                parameters=ToolParameterSchema(
                    type="object",
                    properties={
                        "operation": {
                            "type": "string",
                            "enum": ["add_pattern", "remove_pattern", "list_patterns", "enable"],
                            "description": "Operation to perform"
                        },
                        "pattern": {"type": "string", "description": "Pattern for add/remove operations"},
                        "pattern_type": {"type": "string", "enum": ["regex", "exact"], "default": "regex"},
                        "enabled": {"type": "boolean", "description": "For enable operation"}
                    },
                    required=["operation"]
                ),
                category="security",
                when_to_use="When you need to modify how secrets are detected"
            )
        elif tool_name == "self_help":
            return ToolInfo(
                name="self_help",
                description="Access your experience document for guidance",
                parameters=ToolParameterSchema(
                    type="object",
                    properties={},
                    required=[]
                ),
                category="knowledge",
                when_to_use="When you need guidance on your capabilities or best practices"
            )
        return None

    async def get_all_tool_info(self) -> List[ToolInfo]:
        """Get information about all available tools."""
        tools = []
        for tool_name in await self.get_available_tools():
            tool_info = await self.get_tool_info(tool_name)
            if tool_info:
                tools.append(tool_info)
        return tools

    async def validate_parameters(self, tool_name: str, parameters: dict) -> bool:
        """Validate parameters for a tool."""
        if tool_name == "recall_secret":
            return 'secret_uuid' in parameters and 'purpose' in parameters
        elif tool_name == "update_secrets_filter":
            operation = parameters.get('operation')
            if not operation:
                return False
            if operation in ['add_pattern', 'remove_pattern']:
                return 'pattern' in parameters
            return True
        elif tool_name == "self_help":
            return True  # No parameters required
        return False

    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[ToolExecutionResult]:
        """Get result of an async tool execution."""
        # Secrets tools execute synchronously
        return None

    async def list_tools(self) -> List[str]:
        """List available tools - required by ToolServiceProtocol."""
        return await self.get_available_tools()

    async def get_tool_schema(self, tool_name: str) -> Optional[ToolParameterSchema]:
        """Get parameter schema for a specific tool - required by ToolServiceProtocol."""
        tool_info = await self.get_tool_info(tool_name)
        if tool_info:
            return tool_info.parameters
        return None

    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="SecretsToolService",
            version="1.0.0",
            actions=[
                "recall_secret",
                "update_secrets_filter",
                "self_help"
            ],
            dependencies=["SecretsService", "TimeService"],
            metadata={
                "adapter": self.adapter_name,
                "tool_count": 3
            }
        )

    def get_status(self) -> ServiceStatus:
        """Get current service status."""
        uptime_seconds = 0.0
        if self._start_time:
            uptime_seconds = (self.time_service.now() - self._start_time).total_seconds()
        
        return ServiceStatus(
            service_name="SecretsToolService",
            service_type="tool_service",
            is_healthy=True,
            uptime_seconds=uptime_seconds,
            last_error=None,
            metrics={
                "available_tools": 3
            },
            last_health_check=self.time_service.now()
        )
