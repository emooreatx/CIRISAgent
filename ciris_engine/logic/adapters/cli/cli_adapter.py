"""
Simplified CLI adapter implementing CommunicationService, WiseAuthorityService, and ToolService.
Following the pattern of the refactored Discord adapter.
"""
import logging
import uuid
import asyncio
import sys
from datetime import datetime
from typing import Awaitable, Callable, Dict, List, Optional, Any

from ciris_engine.schemas.adapters.cli import (
    CLIMessage, CLIToolParameters, ListFilesToolParams, ListFilesToolResult,
    ReadFileToolParams, ReadFileToolResult,
    SystemInfoToolResult, CLICorrelationData
)
from ciris_engine.protocols.services import CommunicationService, ToolService
from ciris_engine.schemas.runtime.messages import IncomingMessage, FetchedMessage
from ciris_engine.schemas.telemetry.core import ServiceCorrelation, ServiceCorrelationStatus
from ciris_engine.schemas.runtime.tools import ToolInfo, ToolParameterSchema, ToolExecutionResult
from ciris_engine.logic import persistence

from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.runtime.enums import ServiceType

logger = logging.getLogger(__name__)

class CLIAdapter(CommunicationService, ToolService):
    """
    CLI adapter implementing CommunicationService and ToolService protocols.
    Provides command-line interface for interacting with the CIRIS agent.
    """

    def __init__(
        self,
        runtime: Optional[Any] = None,
        interactive: bool = True,
        on_message: Optional[Callable[[IncomingMessage], Awaitable[None]]] = None,
        bus_manager: Optional[Any] = None,
        config: Optional[Any] = None
    ) -> None:
        """
        Initialize the CLI adapter.
        
        Args:
            runtime: Runtime instance with access to services
            interactive: Whether to run in interactive mode with user input
            on_message: Callback for handling incoming messages
            bus_manager: Multi-service sink for routing messages
            config: Optional CLIAdapterConfig
        """
        super().__init__(config={"retry": {"global": {"max_retries": 3, "base_delay": 1.0}}})
        
        self.runtime = runtime
        self.interactive = interactive
        self.on_message = on_message
        self.bus_manager = bus_manager
        self._running = False
        self._input_task: Optional[asyncio.Task[None]] = None
        self.cli_config = config  # Store the CLI config
        self._time_service: Optional[TimeServiceProtocol] = None
        
        self._available_tools: Dict[str, Callable[[dict], Awaitable[dict]]] = {
            "list_files": self._tool_list_files,
            "read_file": self._tool_read_file,
            "system_info": self._tool_system_info,
        }
        
        self._guidance_queue: asyncio.Queue[str] = asyncio.Queue()
    
    def _get_time_service(self) -> TimeServiceProtocol:
        """Get time service instance from runtime."""
        if self._time_service is None:
            if self.runtime and hasattr(self.runtime, 'service_registry'):
                # Get time service from registry
                time_services = self.runtime.service_registry.get_services_by_type(ServiceType.TIME)
                if time_services:
                    self._time_service = time_services[0]
                else:
                    raise RuntimeError("TimeService not available in runtime")
            else:
                raise RuntimeError("Runtime not available or does not have service registry")
        return self._time_service

    async def _emit_telemetry(self, metric_name: str, tags: Optional[Dict[str, Any]] = None) -> None:
        """Emit telemetry as TSDBGraphNode through memory bus."""
        if not self.bus_manager or not self.bus_manager.memory:
            return  # No bus manager, can't emit telemetry
        
        try:
            # Extract value from tags if it exists, otherwise default to 1.0
            value = 1.0
            if tags and "value" in tags:
                value = float(tags.pop("value"))
            elif tags and "execution_time_ms" in tags:
                value = float(tags["execution_time_ms"])
            elif tags and "success" in tags:
                # For boolean success, use 1.0 for true, 0.0 for false
                value = 1.0 if tags["success"] else 0.0
            
            # Convert all tag values to strings as required by memorize_metric
            string_tags = {k: str(v) for k, v in (tags or {}).items()}
            
            # Use memorize_metric instead of creating GraphNode directly
            await self.bus_manager.memory.memorize_metric(
                metric_name=metric_name,
                value=value,
                tags=string_tags,
                scope="local",
                handler_name="adapter.cli"
            )
        except Exception as e:
            logger.debug(f"Failed to emit telemetry {metric_name}: {e}")
    
    async def send_message(self, channel_id: str, content: str) -> bool:
        """
        Send a message to the console.
        
        Args:
            channel_id: The channel identifier (used for categorization)
            content: The message content
            
        Returns:
            True if message was sent successfully
        """
        correlation_id = str(uuid.uuid4())
        try:
            if channel_id == "system":
                print(f"\n[SYSTEM] {content}")
            elif channel_id == "error":
                print(f"\n[ERROR] {content}", file=sys.stderr)
            else:
                print(f"\n[CIRIS] {content}")
            
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="cli",
                    handler_name="CLIAdapter",
                    action_type="send_message",
                    request_data=CLIMessage(
                        channel_id=channel_id,
                        content=content,
                        timestamp=self._get_time_service().now_iso(),
                        message_type="system" if channel_id == "system" else "error" if channel_id == "error" else "user"
                    ).model_dump(),
                    response_data={"sent": True},
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=self._get_time_service().now_iso(),
                    updated_at=self._get_time_service().now_iso(),
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send CLI message: {e}")
            return False

    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[FetchedMessage]:
        """
        CLI doesn't store messages, so this returns empty list.
        
        Args:
            channel_id: The channel identifier
            limit: Maximum number of messages to fetch
            
        Returns:
            Empty list (CLI doesn't persist messages)
        """
        return []

    async def execute_tool(self, tool_name: str, parameters: dict) -> ToolExecutionResult:
        """
        Execute a CLI tool.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            Tool execution result
        """
        correlation_id = str(uuid.uuid4())
        
        if tool_name not in self._available_tools:
            return ToolExecutionResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
                result={"available_tools": list(self._available_tools.keys())},
                execution_time=0,
                adapter_id="cli",
                output=None,
                metadata={"tool_name": tool_name, "correlation_id": correlation_id}
            )
        
        try:
            import time
            start_time = time.time()
            result = await self._available_tools[tool_name](parameters)
            execution_time = (time.time() - start_time) * 1000
            
            # Emit telemetry for tool execution
            await self._emit_telemetry("tool_executed", {
                "adapter_type": "cli",
                "tool_name": tool_name,
                "execution_time_ms": execution_time,
                "success": result.get("success", True)
            })
            
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="cli",
                    handler_name="CLIAdapter",
                    action_type="execute_tool",
                    request_data=CLICorrelationData(
                        action="execute_tool",
                        request={"tool_name": tool_name, "parameters": parameters},
                        response={},
                        success=True
                    ).model_dump(),
                    response_data=result,
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=self._get_time_service().now_iso(),
                    updated_at=self._get_time_service().now_iso(),
                )
            )
            
            return ToolExecutionResult(
                success=result.get("success", True),
                result=result,
                error=result.get("error"),
                execution_time=execution_time / 1000,  # Convert to seconds
                adapter_id="cli",
                output=None,
                metadata={"tool_name": tool_name, "correlation_id": correlation_id}
            )
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolExecutionResult(
                success=False,
                error=str(e),
                result=None,
                execution_time=0,
                adapter_id="cli",
                output=None,
                metadata={"tool_name": tool_name, "correlation_id": correlation_id}
            )

    async def get_available_tools(self) -> List[str]:
        """Get list of available CLI tools."""
        return list(self._available_tools.keys())

    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[ToolExecutionResult]:
        """CLI tools execute synchronously, so results are immediate."""
        return None

    async def validate_parameters(self, tool_name: str, parameters: dict) -> bool:
        """
        Validate parameters for a CLI tool.
        
        Args:
            tool_name: Name of the tool to validate parameters for
            parameters: Parameters to validate
            
        Returns:
            True if parameters are valid for the specified tool
        """
        if tool_name not in self._available_tools:
            return False
        
        if tool_name == "read_file":
            return "path" in parameters
        elif tool_name == "list_files":
            return True
        elif tool_name == "system_info":
            return True
        
        return True

    async def _get_user_input(self) -> str:
        """Get input from user asynchronously."""
        loop = asyncio.get_event_loop()
        
        # Check if we're still running before blocking on input
        if not self._running:
            raise asyncio.CancelledError("CLI adapter stopped")
        
        # Simple async input that works on all platforms
        try:
            return await loop.run_in_executor(None, input)
        except (EOFError, KeyboardInterrupt):
            raise asyncio.CancelledError("Input interrupted")

    async def _handle_interactive_input(self) -> None:
        """Handle interactive user input in a loop."""
        print("\n[CIRIS CLI] Interactive mode started. Type 'help' for commands or 'quit' to exit.\n")
        
        while self._running:
            try:
                user_input = await self._get_user_input()
                
                if not user_input.strip():
                    continue
                
                if user_input.lower() == 'quit':
                    logger.info("User requested quit")
                    self._running = False
                    break
                elif user_input.lower() == 'help':
                    await self._show_help()
                    continue
                
                msg = IncomingMessage(
                    message_id=str(uuid.uuid4()),
                    author_id="cli_user",
                    author_name="User",
                    content=user_input,
                    channel_id=self.get_home_channel_id(),
                    timestamp=self._get_time_service().now_iso()
                )
                
                if self.on_message:
                    await self.on_message(msg)
                    # Emit telemetry for message processed
                    await self._emit_telemetry("message_processed", {
                        "adapter_type": "cli",
                        "message_id": msg.message_id
                    })
                else:
                    logger.warning("No message handler configured")
                    
            except (EOFError, asyncio.CancelledError):
                logger.info("Input cancelled or EOF received, stopping interactive mode")
                self._running = False
                break
            except Exception as e:
                logger.error(f"Error in interactive input loop: {e}")
                await asyncio.sleep(1)  # Prevent tight error loop

    async def _show_help(self) -> None:
        """Display help information."""
        help_text = """
[CIRIS CLI Help]
================
Commands:
  help     - Show this help message
  quit     - Exit the CLI
  
Tools available:
"""
        print(help_text)
        for tool in self._available_tools:
            print(f"  - {tool}")
        print("\nSimply type your message to interact with CIRIS.\n")

    async def _tool_list_files(self, params: dict) -> dict:
        """List files in a directory."""
        import os
        try:
            # Validate parameters using schema
            list_params = ListFilesToolParams.model_validate(params)
            files = os.listdir(list_params.path)
            result = ListFilesToolResult(success=True, files=files, count=len(files))
            return result.model_dump()
        except ValueError as e:
            result = ListFilesToolResult(success=False, error="Invalid parameters")
            return result.model_dump()
        except Exception as e:
            result = ListFilesToolResult(success=False, error=str(e))
            return result.model_dump()

    async def _tool_read_file(self, params: dict) -> dict:
        """Read a file's contents."""
        try:
            # Validate parameters using schema
            read_params = ReadFileToolParams.model_validate(params)
            with open(read_params.path, 'r') as f:
                content = f.read()
            result = ReadFileToolResult(success=True, content=content, size=len(content))
            return result.model_dump()
        except ValueError as e:
            result = ReadFileToolResult(success=False, error="No path provided")
            return result.model_dump()
        except Exception as e:
            result = ReadFileToolResult(success=False, error=str(e))
            return result.model_dump()

    async def _tool_system_info(self, params: dict) -> dict:
        """Get system information."""
        import platform
        return {
            "success": True,
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version()
        }

    async def start(self) -> None:
        """Start the CLI adapter."""
        logger.info("Starting CLI adapter")
        
        # Emit telemetry for adapter start
        await self._emit_telemetry("adapter_starting", {
            "adapter_type": "cli",
            "interactive": self.interactive
        })
        
        self._running = True
        
        if self.interactive:
            # Start interactive input handler
            self._input_task = asyncio.create_task(self._handle_interactive_input())
        
        # Emit telemetry for successful start
        await self._emit_telemetry("adapter_started", {
            "adapter_type": "cli",
            "interactive": self.interactive
        })

    async def stop(self) -> None:
        """Stop the CLI adapter."""
        logger.info("Stopping CLI adapter")
        
        # Emit telemetry for adapter stopping
        await self._emit_telemetry("adapter_stopping", {
            "adapter_type": "cli"
        })
        
        self._running = False
        
        if self._input_task and not self._input_task.done():
            self._input_task.cancel()
            try:
                await asyncio.wait_for(self._input_task, timeout=0.1)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.debug("CLI input task cancelled")
                pass
        
        # Print message and newline to ensure prompt returns properly
        print("\n[CIRIS CLI] Shutting down... Press Enter to return to prompt.")
        
        # Emit telemetry for successful stop
        await self._emit_telemetry("adapter_stopped", {
            "adapter_type": "cli"
        })

    async def is_healthy(self) -> bool:
        """Check if the CLI adapter is healthy."""
        return self._running
    
    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        from ciris_engine.schemas.services.core import ServiceStatus
        return ServiceStatus(
            service_name="CLIAdapter",
            service_type="adapter",
            is_healthy=self._running,
            uptime_seconds=0.0,  # TODO: Track uptime if needed
            metrics={
                "interactive": self.interactive,
                "running": self._running,
                "available_tools": len(self._available_tools)
            },
            last_error=None,
            last_health_check=self._get_time_service().now() if self._time_service else None
        )
    
    async def list_tools(self) -> List[str]:
        """List available tools."""
        return list(self._available_tools.keys())
    
    async def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific tool."""
        if tool_name not in self._available_tools:
            return None
        
        # Return basic schema info for CLI tools
        schemas = {
            "list_files": {
                "name": "list_files",
                "description": "List files in a directory",
                "parameters": {
                    "path": {"type": "string", "description": "Directory path", "default": "."}
                }
            },
            "read_file": {
                "name": "read_file",
                "description": "Read a file's contents",
                "parameters": {
                    "path": {"type": "string", "description": "File path", "required": True}
                }
            },
            "system_info": {
                "name": "system_info",
                "description": "Get system information",
                "parameters": {}
            }
        }
        
        return schemas.get(tool_name)

    async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """Get detailed information about a specific tool."""
        if tool_name not in self._available_tools:
            return None
        
        # Return basic tool info for CLI tools
        return ToolInfo(
            tool_name=tool_name,
            display_name=tool_name.replace("_", " ").title(),
            description=f"CLI tool: {tool_name}",
            category="cli",
            adapter_id="cli",
            adapter_type="cli",
            adapter_instance_name="CLI Adapter",
            parameters=[],
            returns_schema=None,
            examples=None,
            requires_auth=False,
            rate_limit=None,
            timeout_seconds=30.0,
            enabled=True,
            health_status="healthy"
        )
    
    async def get_all_tool_info(self) -> List[ToolInfo]:
        """Get detailed information about all available tools."""
        tools = []
        for tool_name in self._available_tools:
            tool_info = await self.get_tool_info(tool_name)
            if tool_info:
                tools.append(tool_info)
        return tools

    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        capabilities = [
            "send_message", "fetch_messages",
            "execute_tool", "get_available_tools", "get_tool_result", "validate_parameters",
            "get_tool_info", "get_all_tool_info"
        ]
        if self.interactive:
            capabilities.append("interactive_mode")
        return capabilities
    
    def get_home_channel_id(self) -> str:
        """Get the home channel ID for this CLI adapter instance."""
        if self.cli_config and hasattr(self.cli_config, 'get_home_channel_id'):
            channel_id = self.cli_config.get_home_channel_id()
            if channel_id:
                return str(channel_id)
        
        # Generate unique channel ID for this CLI instance
        import uuid
        import os
        return f"cli_{os.getpid()}_{uuid.uuid4().hex[:8]}"
