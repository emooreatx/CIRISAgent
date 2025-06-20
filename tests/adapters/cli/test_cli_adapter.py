"""
Comprehensive tests for the refactored CLI adapter.
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage, FetchedMessage
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation
from ciris_engine.persistence.db.core import initialize_database


@pytest.fixture(scope="function")
def temp_database():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name
    
    # Initialize the database with all required tables
    initialize_database(db_path)
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def mock_bus_manager():
    """Mock multi-service sink."""
    sink = AsyncMock()
    return sink


@pytest.fixture
def mock_on_message():
    """Mock message callback."""
    return AsyncMock()


@pytest.fixture
def cli_adapter_non_interactive(mock_bus_manager, mock_on_message, temp_database):
    """Create CLI adapter in non-interactive mode."""
    with patch('ciris_engine.config.config_manager.get_sqlite_db_full_path', return_value=temp_database):
        return CLIAdapter(
            interactive=False,
            on_message=mock_on_message,
            bus_manager=mock_bus_manager
        )


@pytest.fixture
def cli_adapter_interactive(mock_bus_manager, mock_on_message, temp_database):
    """Create CLI adapter in interactive mode."""
    with patch('ciris_engine.config.config_manager.get_sqlite_db_full_path', return_value=temp_database):
        return CLIAdapter(
            interactive=True,
            on_message=mock_on_message,
            bus_manager=mock_bus_manager
        )


@pytest.mark.asyncio
class TestCLIAdapter:
    """Test cases for CLI adapter."""

    async def test_init_non_interactive(self, cli_adapter_non_interactive):
        """Test non-interactive adapter initialization."""
        adapter = cli_adapter_non_interactive
        assert adapter.interactive is False
        assert adapter.on_message is not None
        assert adapter.bus_manager is not None
        assert adapter._running is False
        assert len(adapter._available_tools) > 0

    async def test_init_interactive(self, cli_adapter_interactive):
        """Test interactive adapter initialization."""
        adapter = cli_adapter_interactive
        assert adapter.interactive is True
        assert adapter.on_message is not None
        assert adapter.bus_manager is not None
        assert adapter._running is False

    async def test_send_message_success(self, cli_adapter_non_interactive):
        """Test successful message sending."""
        with patch('builtins.print') as mock_print, \
             patch('ciris_engine.persistence.add_correlation') as mock_persist:
            
            result = await cli_adapter_non_interactive.send_message("test_channel", "test message")
            
            assert result is True
            mock_print.assert_called_once_with("\n[CIRIS] test message")
            mock_persist.assert_called_once()
            
            # Verify correlation was logged
            call_args = mock_persist.call_args[0][0]
            assert call_args.service_type == "cli"
            assert call_args.action_type == "send_message"

    async def test_send_message_system_channel(self, cli_adapter_non_interactive):
        """Test sending system message."""
        with patch('builtins.print') as mock_print, \
             patch('ciris_engine.persistence.add_correlation'):
            
            result = await cli_adapter_non_interactive.send_message("system", "system message")
            
            assert result is True
            mock_print.assert_called_once_with("\n[SYSTEM] system message")

    async def test_send_message_error_channel(self, cli_adapter_non_interactive):
        """Test sending error message."""
        with patch('builtins.print') as mock_print, \
             patch('ciris_engine.persistence.add_correlation'), \
             patch('sys.stderr') as mock_stderr:
            
            result = await cli_adapter_non_interactive.send_message("error", "error message")
            
            assert result is True
            mock_print.assert_called_once()
            # Verify it was printed to stderr
            assert "error message" in str(mock_print.call_args)

    async def test_send_message_failure(self, cli_adapter_non_interactive):
        """Test message sending failure."""
        with patch('builtins.print', side_effect=Exception("Print error")):
            result = await cli_adapter_non_interactive.send_message("test_channel", "test message")
            assert result is False

    async def test_fetch_messages(self, cli_adapter_non_interactive):
        """Test message fetching (should return empty for CLI)."""
        messages = await cli_adapter_non_interactive.fetch_messages("test_channel", 10)
        assert len(messages) == 0
        assert isinstance(messages, list)

    async def test_fetch_guidance_non_interactive(self, cli_adapter_non_interactive):
        """Test guidance fetching in non-interactive mode."""
        guidance = await cli_adapter_non_interactive.fetch_guidance({"reason": "test"})
        assert guidance is None

    async def test_fetch_guidance_interactive_with_input(self, cli_adapter_interactive):
        """Test guidance fetching in interactive mode with user input."""
        test_guidance = "This is test guidance"
        
        with patch.object(cli_adapter_interactive, '_get_user_input', return_value=test_guidance), \
             patch('builtins.print'), \
             patch('ciris_engine.persistence.add_correlation') as mock_persist:
            
            from ciris_engine.schemas.wa_context_schemas_v1 import GuidanceContext
            guidance = await cli_adapter_interactive.fetch_guidance(
                GuidanceContext(
                    question="Need guidance",
                    thought_id="test_thought_123",
                    task_id="test_task_456"
                )
            )
            
            assert guidance == test_guidance
            mock_persist.assert_called_once()

    async def test_fetch_guidance_interactive_empty_input(self, cli_adapter_interactive):
        """Test guidance fetching with empty user input."""
        with patch.object(cli_adapter_interactive, '_get_user_input', return_value="   "), \
             patch('builtins.print'):
            
            from ciris_engine.schemas.wa_context_schemas_v1 import GuidanceContext
            guidance = await cli_adapter_interactive.fetch_guidance(
                GuidanceContext(
                    question="test",
                    thought_id="test_thought",
                    task_id="test_task"
                )
            )
            
            assert guidance is None

    async def test_fetch_guidance_timeout(self, cli_adapter_interactive):
        """Test guidance fetching with timeout."""
        with patch.object(cli_adapter_interactive, '_get_user_input', side_effect=asyncio.TimeoutError), \
             patch('builtins.print'):
            
            from ciris_engine.schemas.wa_context_schemas_v1 import GuidanceContext
            guidance = await cli_adapter_interactive.fetch_guidance(
                GuidanceContext(
                    question="test",
                    thought_id="test_thought",
                    task_id="test_task"
                )
            )
            
            assert guidance is None

    async def test_send_deferral_success(self, cli_adapter_non_interactive):
        """Test successful deferral sending."""
        with patch('builtins.print') as mock_print, \
             patch('ciris_engine.persistence.add_correlation') as mock_persist:
            
            from ciris_engine.schemas.wa_context_schemas_v1 import DeferralContext
            result = await cli_adapter_non_interactive.send_deferral(
                DeferralContext(
                    thought_id="thought_123",
                    task_id="task_456",
                    reason="Too complex",
                    metadata={"additional": "context"}
                )
            )
            
            assert result is True
            # Should print deferral notice
            assert mock_print.call_count >= 1
            mock_persist.assert_called_once()

    async def test_send_deferral_failure(self, cli_adapter_non_interactive):
        """Test deferral sending failure."""
        with patch('builtins.print', side_effect=Exception("Print error")):
            from ciris_engine.schemas.wa_context_schemas_v1 import DeferralContext
            result = await cli_adapter_non_interactive.send_deferral(
                DeferralContext(
                    thought_id="thought_123",
                    task_id="task_456",
                    reason="reason"
                )
            )
            assert result is False

    async def test_execute_tool_list_files(self, cli_adapter_non_interactive):
        """Test executing list_files tool."""
        with patch('os.listdir', return_value=['file1.txt', 'file2.txt']), \
             patch('ciris_engine.persistence.add_correlation'):
            
            result = await cli_adapter_non_interactive.execute_tool(
                "list_files", 
                {"path": "/test/path"}
            )
            
            assert result.success is True
            assert "files" in result.result
            assert len(result.result["files"]) == 2

    async def test_execute_tool_read_file(self, cli_adapter_non_interactive):
        """Test executing read_file tool."""
        test_content = "This is test file content"
        
        with patch('builtins.open', mock_open(read_data=test_content)), \
             patch('ciris_engine.persistence.add_correlation'):
            
            result = await cli_adapter_non_interactive.execute_tool(
                "read_file",
                {"path": "/test/file.txt"}
            )
            
            assert result.success is True
            assert result.result["content"] == test_content

    async def test_execute_tool_write_file(self, cli_adapter_non_interactive):
        """Test executing write_file tool."""
        test_content = "Content to write"
        
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('ciris_engine.persistence.add_correlation'):
            
            result = await cli_adapter_non_interactive.execute_tool(
                "write_file",
                {"path": "/test/output.txt", "content": test_content}
            )
            
            assert result.success is True
            assert result.result["bytes_written"] == len(test_content)
            mock_file.assert_called_once_with("/test/output.txt", 'w')

    async def test_execute_tool_system_info(self, cli_adapter_non_interactive):
        """Test executing system_info tool."""
        with patch('platform.system', return_value="Linux"), \
             patch('platform.release', return_value="5.4.0"), \
             patch('platform.version', return_value="Ubuntu"), \
             patch('platform.machine', return_value="x86_64"), \
             patch('platform.python_version', return_value="3.9.0"), \
             patch('ciris_engine.persistence.add_correlation'):
            
            result = await cli_adapter_non_interactive.execute_tool("system_info", {})
            
            assert result.success is True
            assert result.result["system"] == "Linux"
            assert result.result["python_version"] == "3.9.0"

    async def test_execute_tool_unknown(self, cli_adapter_non_interactive):
        """Test executing unknown tool."""
        result = await cli_adapter_non_interactive.execute_tool("unknown_tool", {})
        
        assert result.success is False
        assert "Unknown tool" in result.error
        assert "available_tools" in result.result

    async def test_execute_tool_exception(self, cli_adapter_non_interactive):
        """Test tool execution with exception."""
        with patch('os.listdir', side_effect=Exception("Permission denied")), \
             patch('ciris_engine.persistence.add_correlation'):
            result = await cli_adapter_non_interactive.execute_tool("list_files", {"path": "/test"})
            
            assert result.success is False
            assert "Permission denied" in result.error

    async def test_get_available_tools(self, cli_adapter_non_interactive):
        """Test getting available tools."""
        tools = await cli_adapter_non_interactive.get_available_tools()
        
        expected_tools = ["list_files", "read_file", "write_file", "system_info"]
        for tool in expected_tools:
            assert tool in tools

    async def test_get_tool_result(self, cli_adapter_non_interactive):
        """Test getting tool result (should return None for CLI)."""
        result = await cli_adapter_non_interactive.get_tool_result("correlation_123")
        assert result is None

    async def test_start_stop_non_interactive(self, cli_adapter_non_interactive):
        """Test start/stop lifecycle in non-interactive mode."""
        adapter = cli_adapter_non_interactive
        
        assert not adapter._running
        
        await adapter.start()
        assert adapter._running
        assert await adapter.is_healthy()
        
        await adapter.stop()
        assert not adapter._running
        assert not await adapter.is_healthy()

    async def test_start_stop_interactive(self, cli_adapter_interactive):
        """Test start/stop lifecycle in interactive mode."""
        adapter = cli_adapter_interactive
        
        with patch.object(adapter, '_handle_interactive_input') as mock_interactive:
            mock_interactive.return_value = asyncio.create_task(asyncio.sleep(0.1))
            
            await adapter.start()
            assert adapter._running
            assert adapter._input_task is not None
            
            await adapter.stop()
            assert not adapter._running

    async def test_get_capabilities_non_interactive(self, cli_adapter_non_interactive):
        """Test getting capabilities in non-interactive mode."""
        capabilities = await cli_adapter_non_interactive.get_capabilities()
        
        expected = [
            "send_message", "fetch_messages",
            "fetch_guidance", "send_deferral", 
            "execute_tool", "get_available_tools"
        ]
        
        for cap in expected:
            assert cap in capabilities
        
        assert "interactive_mode" not in capabilities

    async def test_get_capabilities_interactive(self, cli_adapter_interactive):
        """Test getting capabilities in interactive mode."""
        capabilities = await cli_adapter_interactive.get_capabilities()
        
        expected = [
            "send_message", "fetch_messages",
            "fetch_guidance", "send_deferral",
            "execute_tool", "get_available_tools",
            "interactive_mode"
        ]
        
        for cap in expected:
            assert cap in capabilities

    async def test_get_user_input(self, cli_adapter_interactive):
        """Test getting user input."""
        test_input = "test user input"
        cli_adapter_interactive._running = True  # Set running state for test
        
        with patch('builtins.input', return_value=test_input):
            result = await cli_adapter_interactive._get_user_input()
            assert result == test_input

    async def test_show_help(self, cli_adapter_interactive):
        """Test showing help."""
        with patch('builtins.print') as mock_print:
            await cli_adapter_interactive._show_help()
            
            # Should print help information
            assert mock_print.call_count > 0
            # Should mention available tools
            help_output = ' '.join(str(call) for call in mock_print.call_args_list)
            assert "list_files" in help_output

    async def test_handle_interactive_input_quit(self, cli_adapter_interactive):
        """Test interactive input handling with quit command."""
        adapter = cli_adapter_interactive
        adapter._running = True
        
        with patch.object(adapter, '_get_user_input', side_effect=['quit']):
            await adapter._handle_interactive_input()
            
            assert not adapter._running

    async def test_handle_interactive_input_help(self, cli_adapter_interactive):
        """Test interactive input handling with help command."""
        adapter = cli_adapter_interactive
        adapter._running = True
        
        with patch.object(adapter, '_get_user_input', side_effect=['help', 'quit']), \
             patch.object(adapter, '_show_help') as mock_help:
            
            await adapter._handle_interactive_input()
            
            mock_help.assert_called_once()

    async def test_handle_interactive_input_message(self, cli_adapter_interactive):
        """Test interactive input handling with user message."""
        adapter = cli_adapter_interactive
        adapter._running = True
        
        with patch.object(adapter, '_get_user_input', side_effect=['Hello CIRIS', 'quit']):
            await adapter._handle_interactive_input()
            
            # Should call on_message callback
            adapter.on_message.assert_called_once()
            call_args = adapter.on_message.call_args[0][0]
            assert isinstance(call_args, IncomingMessage)
            assert call_args.content == "Hello CIRIS"

    async def test_handle_interactive_input_eof(self, cli_adapter_interactive):
        """Test interactive input handling with EOF (Ctrl+D)."""
        adapter = cli_adapter_interactive
        adapter._running = True
        
        with patch.object(adapter, '_get_user_input', side_effect=EOFError):
            await adapter._handle_interactive_input()
            
            assert not adapter._running

    async def test_handle_interactive_input_exception(self, cli_adapter_interactive):
        """Test interactive input handling with exception."""
        adapter = cli_adapter_interactive
        adapter._running = True
        
        with patch.object(adapter, '_get_user_input', side_effect=[Exception("Test error"), 'quit']), \
             patch('asyncio.sleep', return_value=None):  # Mock sleep to speed up test
            
            await adapter._handle_interactive_input()
            
            assert not adapter._running


@pytest.mark.asyncio
class TestCLIAdapterIntegration:
    """Integration tests for CLI adapter."""

    async def test_full_message_flow_with_callback(self, cli_adapter_interactive):
        """Test complete message flow through callback."""
        adapter = cli_adapter_interactive
        adapter._running = True
        
        test_message = "Integration test message"
        
        with patch.object(adapter, '_get_user_input', side_effect=[test_message, 'quit']):
            await adapter._handle_interactive_input()
            
            # Verify callback was called
            adapter.on_message.assert_called_once()
            msg = adapter.on_message.call_args[0][0]
            assert msg.content == test_message
            assert msg.author_name == "User"
            assert msg.destination_id.startswith("cli")  # Should start with "cli"

    async def test_full_message_flow_with_sink(self, mock_bus_manager):
        """Test complete message flow through multi-service sink."""
        adapter = CLIAdapter(
            interactive=True,
            on_message=None,  # No callback, should use sink
            bus_manager=mock_bus_manager
        )
        adapter._running = True
        
        test_message = "Sink integration test"
        
        with patch.object(adapter, '_get_user_input', side_effect=[test_message, 'quit']):
            await adapter._handle_interactive_input()
            
            # Without on_message callback, the adapter should log a warning
            # The bus_manager is no longer used directly for observe_message
            assert adapter._running == False  # Should have quit after 'quit' command

    async def test_guidance_flow_integration(self, cli_adapter_interactive):
        """Test complete guidance request flow."""
        from ciris_engine.schemas.wa_context_schemas_v1 import GuidanceContext
        
        context = GuidanceContext(
            thought_id="thought_123",
            task_id="task_456",
            question="Should I help with this request?",
            ethical_considerations=["Complex ethical decision"]
        )
        
        guidance_response = "Yes, proceed with caution"
        
        with patch.object(cli_adapter_interactive, '_get_user_input', return_value=guidance_response), \
             patch('builtins.print') as mock_print, \
             patch('ciris_engine.persistence.add_correlation') as mock_persist:
            
            result = await cli_adapter_interactive.fetch_guidance(context)
            
            assert result == guidance_response
            
            # Verify context was displayed
            print_calls = [str(call) for call in mock_print.call_args_list]
            context_output = ' '.join(print_calls)
            assert "GUIDANCE REQUEST" in context_output
            assert context.question in context_output
            assert context.task_id in context_output
            
            # Verify persistence
            mock_persist.assert_called_once()

    async def test_tool_execution_chain(self, cli_adapter_non_interactive):
        """Test chain of tool executions."""
        with patch('os.listdir', return_value=['test.txt']), \
             patch('builtins.open', mock_open(read_data="file content")), \
             patch('ciris_engine.persistence.add_correlation'):
            
            # First, list files
            list_result = await cli_adapter_non_interactive.execute_tool(
                "list_files", {"path": "/test"}
            )
            assert list_result.success
            assert "test.txt" in list_result.result["files"]
            
            # Then, read a file
            read_result = await cli_adapter_non_interactive.execute_tool(
                "read_file", {"path": "/test/test.txt"}
            )
            assert read_result.success
            assert read_result.result["content"] == "file content"

    async def test_concurrent_operations(self, cli_adapter_non_interactive):
        """Test concurrent adapter operations."""
        # Test concurrent message sending
        send_tasks = []
        for i in range(10):
            task = asyncio.create_task(
                cli_adapter_non_interactive.send_message(f"channel_{i}", f"message_{i}")
            )
            send_tasks.append(task)
        
        # Test concurrent tool execution
        tool_tasks = []
        for i in range(5):
            task = asyncio.create_task(
                cli_adapter_non_interactive.execute_tool("system_info", {})
            )
            tool_tasks.append(task)
        
        with patch('builtins.print'), \
             patch('platform.system', return_value="Linux"), \
             patch('platform.release', return_value="5.4.0"), \
             patch('platform.version', return_value="Ubuntu"), \
             patch('platform.machine', return_value="x86_64"), \
             patch('platform.python_version', return_value="3.9.0"), \
             patch('ciris_engine.persistence.add_correlation'):
            
            # Run all tasks concurrently
            send_results = await asyncio.gather(*send_tasks)
            tool_results = await asyncio.gather(*tool_tasks)
            
            # All should succeed
            assert all(send_results)
            assert all(result.success for result in tool_results)


# Helper function for mocking file operations
def mock_open(read_data=""):
    """Create a mock file object."""
    from unittest.mock import mock_open as original_mock_open
    return original_mock_open(read_data=read_data)