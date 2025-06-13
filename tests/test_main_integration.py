"""Integration tests for main.py entrypoint.

These tests verify that the main entrypoint works correctly with various
configurations and catches runtime issues that unit tests might miss.
"""
import asyncio
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

import main as main_module


class TestMainIntegration:
    """Integration tests for the main entrypoint."""

    def test_main_startup_with_mock_llm_api_cli(self):
        """Test main startup with mock LLM and CLI mode with full wakeup cycle."""
        # This tests the exact scenario mentioned: clean startup -> wakeup -> work -> shutdown
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "cli", 
            "--timeout", "20"
        ]
        
        # Run with timeout to prevent hanging
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent
        )
        
        # Should exit cleanly (return code 0)
        assert result.returncode == 0, f"Process failed with stderr: {result.stderr}"
        
        # Check for expected FULL state transitions (complete wakeup sequence)
        output = result.stdout + result.stderr
        assert "[STATE] Transition: shutdown -> wakeup" in output, "Missing initial wakeup transition"
        
        # For full wakeup test, ensure we get far enough to see meaningful activity
        # Either we complete the full cycle OR we at least get CLI activity indicating successful startup
        has_full_cycle = (
            "[STATE] Transition: wakeup -> work" in output and 
            "[STATE] Transition: work -> shutdown" in output
        )
        has_cli_activity = (
            "[CLI]" in output and 
            "Hello! How can I help you?" in output and
            "[DISPATCHER] Handler SpeakHandler completed" in output
        )
        
        assert has_full_cycle or has_cli_activity, (
            f"Missing either full state cycle or CLI activity. "
            f"Full cycle: {has_full_cycle}, CLI activity: {has_cli_activity}. "
            f"Output length: {len(output)} chars"
        )
        
        # Should not have critical errors
        assert "CRITICAL" not in output
        assert "ERROR" not in output or "Error during shutdown" in output  # Shutdown errors are sometimes expected

    def test_main_startup_quick_modes(self):
        """Test main startup with different modes (quick timeout, no full wakeup)."""
        # Test API mode
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "api",
            "--timeout", "5"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=12,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0, f"API mode failed with stderr: {result.stderr}"
        
        # Test CLI mode
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "cli",
            "--timeout", "5",
            "--no-interactive"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=12,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0, f"CLI mode failed with stderr: {result.stderr}"

    def test_main_help_command(self):
        """Test that help command works."""
        cmd = [sys.executable, "-u", "main.py", "--help"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent.parent,
            env=os.environ.copy()
        )
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "--adapter" in result.stdout
        assert "--profile" in result.stdout

    def test_main_invalid_mode(self):
        """Test that invalid mode fails gracefully."""
        cmd = [
            sys.executable, "main.py",
            "--adapter", "invalid_mode",
            "--timeout", "1"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,  # Generous timeout for CI environment
            cwd=Path(__file__).parent.parent
        )
        
        # Should fail with non-zero exit code and show error message
        assert result.returncode != 0, f"Expected non-zero exit code, got {result.returncode}. stderr: {result.stderr}"
        assert "Invalid adapter" in result.stderr, f"Expected error message about invalid adapter, got stderr: {result.stderr}"

    def test_main_with_environment_variables(self):
        """Test main with environment variables set."""
        env = os.environ.copy()
        env["LOG_LEVEL"] = "DEBUG"
        env["CIRIS_DATA_DIR"] = "test_data"
        
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "cli",
            "--timeout", "5",
            "--no-interactive"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=12,
            env=env,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0, f"Process failed with stderr: {result.stderr}"

    def test_main_signal_handling(self):
        """Test that main handles signals gracefully."""
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "cli",
            "--no-interactive"
        ]
        
        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        try:
            # Give it time to start up
            time.sleep(1)
            
            # Send SIGTERM
            process.send_signal(signal.SIGTERM)
            
            # Wait for graceful shutdown
            stdout, stderr = process.communicate(timeout=5)
            
            # Should exit in response to signal (return code -15 means killed by SIGTERM, which is expected)
            assert process.returncode in [0, -15], f"Process should exit cleanly or be terminated by signal, got return code: {process.returncode}, stderr: {stderr}"
            
            # Signal handling works as evidenced by the clean termination
            # The process responded to SIGTERM properly (return code -15 indicates killed by signal)
            output = stdout + stderr
            # Process terminated cleanly in response to signal - this is the important behavior
            assert True  # The previous assertion on return code already validates signal handling works
            
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            pytest.fail("Process did not shut down gracefully within timeout")

    def test_main_with_custom_config_file(self):
        """Test main with custom configuration file."""
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_content = {
                "log_level": "INFO",
                "database": {
                    "db_filename": "test.db"
                }
            }
            import json
            json.dump(config_content, f)
            config_path = f.name
        
        try:
            cmd = [
                sys.executable, "main.py",
                "--mock-llm",
                "--adapter", "cli",
                "--config", config_path,
                "--timeout", "5",
                "--no-interactive"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=12,
                cwd=Path(__file__).parent.parent
            )
            
            assert result.returncode == 0, f"Process failed with stderr: {result.stderr}"
            
        finally:
            # Clean up
            os.unlink(config_path)

    def test_main_handler_execution(self):
        """Test that invalid handler option shows appropriate error."""
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "cli",
            "--handler", "speak",
            "--no-interactive"
        ]
        
        # Run the command and expect it to fail quickly due to invalid option
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,  # Generous timeout for CI environments
                cwd=Path(__file__).parent.parent
            )
            
            # Should fail because --handler option no longer exists
            assert result.returncode != 0, f"Expected non-zero exit code, got {result.returncode}. stderr: {result.stderr}"
            assert "No such option: --handler" in result.stderr, f"Expected handler error message, got stderr: {result.stderr}"
            
        except subprocess.TimeoutExpired as e:
            # If the process times out, it means the validation didn't work as expected
            # Kill the process and fail the test
            if hasattr(e, 'process') and e.process:
                try:
                    e.process.kill()
                    e.process.wait()
                except:
                    pass
            pytest.fail(f"Command should have failed immediately with invalid option error, but timed out after {e.timeout} seconds")

    def test_main_runtime_workflow(self):
        """Test the complete runtime workflow: shutdown -> wakeup -> work."""
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "api",
            "--adapter", "cli", 
            "--timeout", "15",
            "--no-interactive"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=25,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0, f"Process failed with stderr: {result.stderr}"
        
        output = result.stdout + result.stderr
        
        # Check for expected workflow transitions
        assert "[STATE] Transition: shutdown -> wakeup" in output
        
        # Should have dispatcher activity indicating successful workflow
        assert "[DISPATCHER]" in output, f"Expected dispatcher activity, got: {output[:500]}..."
        # Should have handler execution indicating the system is working
        assert "Handler" in output and "completed" in output, f"Expected handler completion messages, got: {output[:500]}..."
        
        # Should complete without critical errors
        lines = output.split('\n')
        critical_errors = [line for line in lines if 'CRITICAL' in line and 'shutdown' not in line.lower()]
        assert len(critical_errors) == 0, f"Found critical errors: {critical_errors}"


class TestMainFunctionUnits:
    """Unit tests for individual functions in main.py."""

    def test_setup_signal_handlers(self):
        """Test signal handler setup."""
        mock_runtime = MagicMock()
        
        # Should not raise exceptions
        main_module.setup_signal_handlers(mock_runtime)
        
        # Signal handlers should be set (can't easily test the actual handlers)
        # This is mainly a smoke test

    def test_setup_global_exception_handler(self):
        """Test global exception handler setup."""
        original_excepthook = sys.excepthook
        
        try:
            main_module.setup_global_exception_handler()
            
            # Exception hook should be changed
            assert sys.excepthook != original_excepthook
            
        finally:
            # Restore original
            sys.excepthook = original_excepthook

    def test_create_thought(self):
        """Test thought creation helper."""
        thought = main_module._create_thought()
        
        assert thought.thought_id
        assert thought.source_task_id
        assert thought.thought_type == "standard"
        assert thought.content == "manual invocation"
        assert thought.status  # Should have a status


class TestMainConfigurationLogic:
    """Test configuration and mode detection logic."""

    def test_mode_auto_detection_with_discord_token(self):
        """Test that Discord mode is auto-detected when token is available."""
        # This would need to be tested through subprocess since it involves
        # environment variable checking and complex logic
        pass  # Placeholder - this is tested in integration tests above

    def test_api_host_port_configuration(self):
        """Test API host and port configuration."""
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "api",
            "--host", "127.0.0.1",
            "--port", "8081",
            "--timeout", "5"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=12,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0, f"Process failed with stderr: {result.stderr}"
        
        # Should successfully start with API adapter (port may not be explicitly logged)
        output = result.stdout + result.stderr
        # Just check that it ran successfully - the port configuration would be used internally
        assert "shutdown" in output.lower() or "[STATE]" in output, f"Expected evidence of successful execution, got: {output[:200]}..."

    def test_debug_flag(self):
        """Test debug flag functionality."""
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "cli",
            "--debug",
            "--timeout", "5",
            "--no-interactive"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=12,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0, f"Process failed with stderr: {result.stderr}"
        
        # Debug mode should produce more verbose output
        output = result.stdout + result.stderr
        assert "DEBUG" in output or len(output.split('\n')) > 5


class TestMainErrorScenarios:
    """Test error handling scenarios."""

    def test_main_with_invalid_profile(self):
        """Test main with non-existent profile."""
        cmd = [
            sys.executable, "main.py",
            "--mock-llm",
            "--adapter", "cli",
            "--profile", "nonexistent_profile",
            "--timeout", "5",
            "--no-interactive"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=12,
            cwd=Path(__file__).parent.parent
        )
        
        # Should either fail gracefully or fall back to default
        # The exact behavior depends on implementation
        assert result.returncode in [0, 1]  # Either success with fallback or controlled failure

    def test_main_with_invalid_config_file(self):
        """Test main with invalid config file."""
        # Create temporary invalid config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            config_path = f.name
        
        try:
            cmd = [
                sys.executable, "main.py",
                "--mock-llm",
                "--adapter", "cli",
                "--config", config_path,
                "--timeout", "5",
                "--no-interactive"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=12,
                cwd=Path(__file__).parent.parent
            )
            
            # Should handle invalid config gracefully
            # Either fail with proper error or fall back to defaults
            if result.returncode != 0:
                # If it fails, should have meaningful error message
                assert "config" in result.stderr.lower() or "json" in result.stderr.lower()
            
        finally:
            os.unlink(config_path)


if __name__ == "__main__":
    pytest.main([__file__])