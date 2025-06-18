"""
Simplified CLI adapter implementing CommunicationService, WiseAuthorityService, and ToolService.
Following the pattern of the refactored Discord adapter.
"""
import logging
import uuid
import asyncio
import sys
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Callable, Awaitable

from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, ToolService
from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage, IncomingMessage
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, ServiceCorrelationStatus
from ciris_engine import persistence

logger = logging.getLogger(__name__)


class CLIAdapter(CommunicationService, WiseAuthorityService, ToolService):
    """
    CLI adapter implementing CommunicationService, WiseAuthorityService, and ToolService protocols.
    Provides command-line interface for interacting with the CIRIS agent.
    """

    def __init__(
        self,
        interactive: bool = True,
        on_message: Optional[Callable[[IncomingMessage], Awaitable[None]]] = None,
        multi_service_sink: Optional[Any] = None,
        config: Optional[Any] = None
    ) -> None:
        """
        Initialize the CLI adapter.
        
        Args:
            interactive: Whether to run in interactive mode with user input
            on_message: Callback for handling incoming messages
            multi_service_sink: Multi-service sink for routing messages
            config: Optional CLIAdapterConfig
        """
        super().__init__(config={"retry": {"global": {"max_retries": 3, "base_delay": 1.0}}})
        
        self.interactive = interactive
        self.on_message = on_message
        self.multi_service_sink = multi_service_sink
        self._running = False
        self._input_task: Optional[asyncio.Task[None]] = None
        self.cli_config = config  # Store the CLI config
        
        self._available_tools: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
            "list_files": self._tool_list_files,
            "read_file": self._tool_read_file,
            "write_file": self._tool_write_file,
            "system_info": self._tool_system_info,
        }
        
        self._guidance_queue: asyncio.Queue[str] = asyncio.Queue()

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
                    request_data={"channel_id": channel_id, "content": content},
                    response_data={"sent": True},
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
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

    async def fetch_guidance(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Request guidance from the user via CLI.
        
        Args:
            context: Context for the guidance request
            
        Returns:
            User's guidance response if available
        """
        if not self.interactive:
            logger.warning("Cannot fetch guidance in non-interactive mode")
            return None
        
        correlation_id = str(uuid.uuid4())
        try:
            print("\n" + "=" * 60)
            print("[GUIDANCE REQUEST]")
            print(f"Context: {context.get('reason', 'No reason provided')}")
            if 'thought_summary' in context:
                print(f"Thought: {context['thought_summary']}")
            print("=" * 60)
            print("Please provide guidance (or press Enter to skip): ")
            
            try:
                guidance = await asyncio.wait_for(
                    self._get_user_input(),
                    timeout=300.0  # 5 minute timeout
                )
                if guidance.strip():
                    persistence.add_correlation(
                        ServiceCorrelation(
                            correlation_id=correlation_id,
                            service_type="cli",
                            handler_name="CLIAdapter",
                            action_type="fetch_guidance",
                            request_data=context,
                            response_data={"guidance": guidance},
                            status=ServiceCorrelationStatus.COMPLETED,
                            created_at=datetime.now(timezone.utc).isoformat(),
                            updated_at=datetime.now(timezone.utc).isoformat(),
                        )
                    )
                    return guidance
            except (asyncio.TimeoutError, asyncio.CancelledError):
                if not self._running:
                    logger.debug("Guidance request cancelled due to shutdown")
                else:
                    print("\n[TIMEOUT] No guidance provided within timeout period.")
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching guidance: {e}")
            return None

    async def send_deferral(self, thought_id: str, reason: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Display a deferral notice to the user.
        
        Args:
            thought_id: ID of the thought being deferred
            reason: Reason for deferral
            context: Additional context
            
        Returns:
            True if deferral was displayed successfully
        """
        correlation_id = str(uuid.uuid4())
        try:
            print("\n" + "*" * 60)
            print("[DEFERRED TO WISE AUTHORITY]")
            print(f"Thought ID: {thought_id}")
            print(f"Reason: {reason}")
            if context:
                print(f"Context: {context}")
            print("*" * 60 + "\n")
            
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="cli",
                    handler_name="CLIAdapter",
                    action_type="send_deferral",
                    request_data={
                        "thought_id": thought_id,
                        "reason": reason,
                        "context": context
                    },
                    response_data={"displayed": True},
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            return True
            
        except Exception as e:
            logger.error(f"Error sending deferral: {e}")
            return False

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
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
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(self._available_tools.keys())
            }
        
        try:
            result = await self._available_tools[tool_name](parameters)
            
            persistence.add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="cli",
                    handler_name="CLIAdapter",
                    action_type="execute_tool",
                    request_data={"tool_name": tool_name, "parameters": parameters},
                    response_data=result,
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}

    async def get_available_tools(self) -> List[str]:
        """Get list of available CLI tools."""
        return list(self._available_tools.keys())

    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """CLI tools execute synchronously, so results are immediate."""
        return None

    async def validate_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
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
        
        if tool_name == "read_file" or tool_name == "write_file":
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
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                
                if self.on_message:
                    await self.on_message(msg)
                elif self.multi_service_sink:
                    await self.multi_service_sink.observe_message(
                        "ObserveHandler", msg, {"source": "cli"}
                    )
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

    async def _tool_list_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List files in a directory."""
        import os
        path = params.get("path", ".")
        try:
            files = os.listdir(path)
            return {"success": True, "files": files, "count": len(files)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read a file's contents."""
        path = params.get("path")
        if not path:
            return {"success": False, "error": "No path provided"}
        try:
            with open(path, 'r') as f:
                content = f.read()
            return {"success": True, "content": content, "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_write_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Write content to a file."""
        path = params.get("path")
        content = params.get("content", "")
        if not path:
            return {"success": False, "error": "No path provided"}
        try:
            with open(path, 'w') as f:
                f.write(content)
            return {"success": True, "bytes_written": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_system_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
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
        self._running = True
        
        if self.interactive:
            # Start interactive input handler
            self._input_task = asyncio.create_task(self._handle_interactive_input())

    async def stop(self) -> None:
        """Stop the CLI adapter."""
        logger.info("Stopping CLI adapter")
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

    async def is_healthy(self) -> bool:
        """Check if the CLI adapter is healthy."""
        return self._running

    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        capabilities = [
            "send_message", "fetch_messages",
            "fetch_guidance", "send_deferral",
            "execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"
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
