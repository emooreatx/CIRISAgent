"""
Test all 10 CIRIS handlers through the API using Mock LLM.

This test suite verifies that each handler (MEMORIZE, SPEAK, OBSERVE, DEFER, 
REJECT, TASK_COMPLETE, TOOL, RECALL, FORGET, PONDER) works correctly when 
invoked through the API with appropriate mock LLM commands.
"""

# CRITICAL: Prevent side effects during imports
import os
os.environ['CIRIS_IMPORT_MODE'] = 'true'
os.environ['CIRIS_MOCK_LLM'] = 'true'

import pytest
import requests
import time
import json
import socket
import sqlite3
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path


# Skip all tests in this module if API is not available
def check_api_available():
    """Check if API is accessible."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8080))
        sock.close()
        return result == 0
    except Exception:
        return False


# Apply skip to entire module
pytestmark = [
    pytest.mark.skipif(not check_api_available(), reason="API not running on localhost:8080"),
    pytest.mark.integration  # Mark as integration test
]


class CIRISAPIClient:
    """Helper class for interacting with CIRIS API."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.headers: Dict[str, str] = {}
        
    def login(self, username: str = "admin", password: str = "ciris_admin_password") -> bool:
        """Login and store authentication token."""
        resp = requests.post(
            f"{self.base_url}/v1/auth/login",
            json={"username": username, "password": password}
        )
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            return True
        return False
        
    def interact(self, message: str, channel_id: str = "api_test") -> Dict[str, Any]:
        """Send a message to the agent."""
        resp = requests.post(
            f"{self.base_url}/v1/agent/interact",
            json={"message": message, "channel_id": channel_id},
            headers=self.headers
        )
        return resp.json() if resp.status_code == 200 else {"error": resp.text}
        
    def get_audit_entries(self, limit: int = 10, resource_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get audit entries, optionally filtered by resource."""
        resp = requests.get(
            f"{self.base_url}/v1/audit/entries?limit={limit}",
            headers=self.headers
        )
        if resp.status_code == 200:
            entries = resp.json().get("data", {}).get("entries", [])
            if resource_filter:
                entries = [e for e in entries if resource_filter in e.get("resource", "")]
            return entries
        return []
        
    def search_memory(self, query: str) -> List[Dict[str, Any]]:
        """Search memory graph."""
        resp = requests.post(
            f"{self.base_url}/v1/memory/search",
            json={"query": query},
            headers=self.headers
        )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("results", [])
        return []
        
    def wait_for_processing(self, timeout: int = 2, poll_interval: float = 0.1) -> None:
        """Wait for agent to process the request with polling."""
        # For now, still use sleep but with shorter default
        # In future, could implement polling for completion status
        time.sleep(min(timeout, 1.0))  # Cap at 1 second for tests
        
    def get_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent reasoning traces."""
        resp = requests.get(
            f"{self.base_url}/v1/telemetry/traces?limit={limit}",
            headers=self.headers
        )
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("traces", [])
        return []
        
    def get_handler_actions_from_message(self, message_id: str, wait_time: int = 2) -> List[str]:
        """Get handler actions for a specific message by searching recent audit entries."""
        # Wait for processing
        time.sleep(wait_time)
        
        # Get recent audit entries
        entries = self.get_audit_entries(limit=100)
        
        # Filter entries related to handlers after this message
        handler_actions = []
        for entry in entries:
            action = entry.get('action', '')
            if 'HANDLER_ACTION_' in str(action):
                handler_actions.append(action)
                
        return handler_actions
    
    def find_handler_action(self, handler_name: str, limit: int = 50, time_window_seconds: int = 20) -> bool:
        """Check if a specific handler was invoked recently via direct DB query."""
        # This is a test helper that queries the database directly
        # In production, use telemetry/audit endpoints
        
        # Calculate time window
        from datetime import datetime, timezone, timedelta
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=time_window_seconds)
        
        # First try audit entries via API
        entries = self.get_audit_entries(limit=limit)
        for entry in entries:
            # Check timestamp first
            entry_time_str = entry.get('timestamp', '')
            if entry_time_str:
                try:
                    entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                    if entry_time < cutoff_time:
                        continue  # Skip old entries
                except:
                    pass  # If timestamp parsing fails, check anyway
                    
            # Check handler match
            if handler_name in str(entry.get('actor', '')) or \
               handler_name.upper() in str(entry.get('action', '')):
                return True
        
        # If running in container, try direct DB query
        try:
            # Assume standard CIRIS DB path
            db_path = Path("/app/data/ciris.db")
            if not db_path.exists():
                db_path = Path("data/ciris.db")
            
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.execute("""
                    SELECT handler_name, created_at
                    FROM service_correlations 
                    WHERE handler_name LIKE ? 
                    AND datetime(created_at) >= datetime('now', '-' || ? || ' seconds')
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (f"%{handler_name}%", time_window_seconds, limit))
                
                rows = cursor.fetchall()
                conn.close()
                
                return len(rows) > 0
        except Exception:
            # DB query failed, rely on audit entries
            pass
        
        return False


@pytest.fixture
def api_client():
    """Create and authenticate API client."""
    client = CIRISAPIClient()
    assert client.login(), "Failed to authenticate with API"
    return client


class TestMemorizeHandler:
    """Test MEMORIZE handler functionality."""
    
    def test_memorize_simple_content(self, api_client):
        """Test memorizing simple text content."""
        # Send memorize command with correct format: $memorize <node_id> [type] [scope]
        result = api_client.interact("$memorize sky_blue CONCEPT LOCAL")
        assert "data" in result
        assert result["data"]["message_id"] is not None
        assert result["data"]["state"] == "WORK"
        
    def test_memorize_with_node_details(self, api_client):
        """Test memorizing with specific node type and scope."""
        result = api_client.interact("$memorize weather_fact CONCEPT LOCAL")
        assert "data" in result
        assert result["data"]["message_id"] is not None


class TestSpeakHandler:
    """Test SPEAK handler functionality."""
    
    def test_speak_simple_message(self, api_client):
        """Test speaking a simple message."""
        result = api_client.interact("$speak Hello, world!")
        assert "data" in result
        assert result["data"]["message_id"] is not None
        assert result["data"]["state"] == "WORK"
        
    def test_speak_cross_channel(self, api_client):
        """Test speaking to a different channel."""
        result = api_client.interact("$speak @channel:api_other_channel Test cross-channel message")
        assert "data" in result
        assert result["data"]["message_id"] is not None
        
    def test_speak_to_nonexistent_discord_channel(self, api_client):
        """Test speaking to a Discord channel when no Discord adapter is registered."""
        # Send message to Discord channel (should fail and create follow-up thought)
        result = api_client.interact("$speak @channel:discord_1364300186003968060_1382010877171073108 Hello Discord!")
        assert "data" in result
        assert result["data"]["message_id"] is not None
        
        # Wait for processing
        api_client.wait_for_processing(timeout=3)
        
        # Check audit entries for SPEAK handler and failure indication
        entries = api_client.get_audit_entries(limit=50)
        
        # Look for SPEAK handler invocation
        speak_found = False
        speak_failed = False
        for entry in entries:
            if "SpeakHandler" in entry.get("actor", "") or "HANDLER_ACTION_SPEAK" in str(entry.get("action", "")):
                speak_found = True
                # Check if it failed
                if entry.get("event_data", {}).get("outcome") == "failed":
                    speak_failed = True
                    
        assert speak_found, "SpeakHandler should have been invoked"
        # The handler should have created a follow-up thought about the failure


class TestRecallHandler:
    """Test RECALL handler functionality."""
    
    def test_recall_memories(self, api_client):
        """Test recalling memories."""
        # First memorize something with correct format
        api_client.interact("$memorize france_capital CONCEPT LOCAL")
        api_client.wait_for_processing()
        
        # Then recall it - with enhanced recall, partial match should work
        result = api_client.interact("$recall france")
        assert "data" in result
        assert result["data"]["message_id"] is not None


class TestPonderHandler:
    """Test PONDER handler functionality."""
    
    def test_ponder_single_question(self, api_client):
        """Test pondering a single question."""
        result = api_client.interact("$ponder What is the meaning of life?")
        assert "data" in result
        assert result["data"]["message_id"] is not None
        
    def test_ponder_multiple_questions(self, api_client):
        """Test pondering multiple questions."""
        result = api_client.interact("$ponder What should I do next?; How can I be helpful?; Is this ethical?")
        assert "data" in result
        assert result["data"]["message_id"] is not None


class TestObserveHandler:
    """Test OBSERVE handler functionality."""
    
    def test_observe_channel(self, api_client):
        """Test observing a channel."""
        # Use active observation to trigger the handler
        result = api_client.interact("$observe api_test true")
        assert "data" in result
        message_id = result["data"]["message_id"]
        
        # Wait for processing (increased for reliability)
        time.sleep(5)
        
        # Check if ObserveHandler was invoked - increase limit and time window due to test concurrency
        observe_found = api_client.find_handler_action('ObserveHandler', limit=200, time_window_seconds=30)
        assert observe_found, "ObserveHandler not found in recent audit entries or correlations"


class TestToolHandler:
    """Test TOOL handler functionality."""
    
    def test_tool_curl(self, api_client):
        """Test using the curl tool."""
        result = api_client.interact('$tool curl url=http://example.com')
        assert "data" in result
        message_id = result["data"]["message_id"]
        
        # Wait for processing
        time.sleep(2)
        
        # Check if ToolHandler was invoked
        tool_found = api_client.find_handler_action('ToolHandler', limit=100)
        assert tool_found, "ToolHandler not found in recent audit entries or correlations"
        
    def test_tool_with_params(self, api_client):
        """Test tool with key=value parameters."""
        result = api_client.interact("$tool http_get url=http://example.com timeout=5")
        assert "data" in result
        
        api_client.wait_for_processing()


class TestDeferHandler:
    """Test DEFER handler functionality."""
    
    def test_defer_with_reason(self, api_client):
        """Test deferring with a reason."""
        result = api_client.interact("$defer I need more information to answer this question")
        assert "data" in result
        
        api_client.wait_for_processing(timeout=4)
        
        # Check if DeferHandler was invoked
        defer_found = api_client.find_handler_action('DeferHandler', limit=100)
        assert defer_found, "DeferHandler not found in recent audit entries or correlations"


class TestRejectHandler:
    """Test REJECT handler functionality."""
    
    def test_reject_with_reason(self, api_client):
        """Test rejecting with a reason."""
        result = api_client.interact("$reject This request violates ethical guidelines")
        assert "data" in result
        
        api_client.wait_for_processing(timeout=3)
        
        # Check if RejectHandler was invoked
        reject_found = api_client.find_handler_action('RejectHandler', limit=100)
        assert reject_found, "RejectHandler not found in recent audit entries or correlations"


class TestForgetHandler:
    """Test FORGET handler functionality."""
    
    def test_forget_memory(self, api_client):
        """Test forgetting a memory."""
        # First memorize something with a specific node ID
        api_client.interact("$memorize test_memory_node CONCEPT LOCAL")
        api_client.wait_for_processing()
        
        # Then forget it
        result = api_client.interact("$forget test_memory_node User requested deletion")
        assert "data" in result
        
        api_client.wait_for_processing(timeout=2)
        
        # Check if ForgetHandler was invoked
        forget_found = api_client.find_handler_action('ForgetHandler', limit=100)
        assert forget_found, "ForgetHandler not found in recent audit entries or correlations"


class TestTaskCompleteHandler:
    """Test TASK_COMPLETE handler functionality."""
    
    def test_task_complete(self, api_client):
        """Test completing a task."""
        result = api_client.interact("$task_complete")
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Check if TaskCompleteHandler was invoked
        complete_found = api_client.find_handler_action('TaskCompleteHandler', limit=100)
        assert complete_found, "TaskCompleteHandler not found in recent audit entries or correlations"


class TestHandlerIntegration:
    """Test integration scenarios with multiple handlers."""
    
    def test_memorize_and_recall_flow(self, api_client):
        """Test complete memorize and recall flow."""
        # Memorize multiple facts
        facts = [
            "$memorize Python is a programming language",
            "$memorize Docker is a containerization platform",
            "$memorize CIRIS is a moral reasoning system"
        ]
        
        for fact in facts:
            api_client.interact(fact)
            api_client.wait_for_processing(1)  # Reduced from 5s
            
        # Recall specific information
        result = api_client.interact("$recall programming")
        assert "data" in result
        api_client.wait_for_processing()
        
        # Verify we got some handler activity - look for Handler in actor field
        entries = api_client.get_audit_entries(limit=50)
        handler_entries = [e for e in entries if "Handler" in e.get("actor", "") or "HANDLER" in str(e.get("action", ""))]
        assert len(handler_entries) >= 4, f"Expected at least 4 handler entries, got {len(handler_entries)}"
        
    def test_ponder_and_speak_flow(self, api_client):
        """Test pondering followed by speaking."""
        # Ponder questions
        api_client.interact("$ponder What insights can I share?; How can I be helpful?")
        api_client.wait_for_processing()
        
        # Speak response
        api_client.interact("$speak Based on my pondering, I can help by providing information")
        api_client.wait_for_processing()
        
        # Check both handlers were used - look for Handler actors or HANDLER actions
        entries = api_client.get_audit_entries(limit=100)
        
        # Debug: print entries to see what we're getting
        print(f"\nTotal audit entries: {len(entries)}")
        for entry in entries[:10]:
            print(f"  - Action: {entry.get('action', 'N/A')}, Actor: {entry.get('actor', 'N/A')}")
        
        # Look for PonderHandler or HANDLER_ACTION_PONDER
        ponder_found = any(
            "PonderHandler" in e.get("actor", "") or 
            "AuditEventType.HANDLER_ACTION_PONDER" in str(e.get("action", ""))
            for e in entries
        )
        
        # Look for SpeakHandler or HANDLER_ACTION_SPEAK
        speak_found = any(
            "SpeakHandler" in e.get("actor", "") or 
            "AuditEventType.HANDLER_ACTION_SPEAK" in str(e.get("action", ""))
            for e in entries
        )
        
        assert ponder_found, f"PONDER handler not found in audit entries"
        assert speak_found, f"SPEAK handler not found in audit entries"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])