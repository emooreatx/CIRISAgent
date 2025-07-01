"""
Test all 10 CIRIS handlers through the API using Mock LLM.

This test suite verifies that each handler (MEMORIZE, SPEAK, OBSERVE, DEFER, 
REJECT, TASK_COMPLETE, TOOL, RECALL, FORGET, PONDER) works correctly when 
invoked through the API with appropriate mock LLM commands.
"""

import pytest
import requests
import time
import json
from typing import Dict, Any, Optional, List
from datetime import datetime


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
        
    def wait_for_processing(self, timeout: int = 10) -> None:
        """Wait for agent to process the request."""
        time.sleep(timeout)


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
        # Send memorize command
        result = api_client.interact("$memorize The sky is blue")
        assert "data" in result
        
        # Wait for processing
        api_client.wait_for_processing()
        
        # Check audit entries for memorize action
        entries = api_client.get_audit_entries(resource_filter="handler")
        memorize_entries = [e for e in entries if "MEMORIZE" in str(e)]
        assert len(memorize_entries) > 0, "No MEMORIZE handler entries found"
        
    def test_memorize_with_node_details(self, api_client):
        """Test memorizing with specific node type and scope."""
        result = api_client.interact("$memorize weather_fact CONCEPT LOCAL")
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Verify in audit
        entries = api_client.get_audit_entries()
        assert any("memorize" in str(e).lower() for e in entries)


class TestSpeakHandler:
    """Test SPEAK handler functionality."""
    
    def test_speak_simple_message(self, api_client):
        """Test speaking a simple message."""
        result = api_client.interact("$speak Hello, world!")
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Check audit entries
        entries = api_client.get_audit_entries(resource_filter="handler")
        speak_entries = [e for e in entries if "SPEAK" in str(e)]
        assert len(speak_entries) > 0, "No SPEAK handler entries found"
        
    def test_speak_cross_channel(self, api_client):
        """Test speaking to a different channel."""
        result = api_client.interact("$speak @channel:api_other_channel Test cross-channel message")
        assert "data" in result
        
        api_client.wait_for_processing()


class TestRecallHandler:
    """Test RECALL handler functionality."""
    
    def test_recall_memories(self, api_client):
        """Test recalling memories."""
        # First memorize something
        api_client.interact("$memorize The capital of France is Paris")
        api_client.wait_for_processing()
        
        # Then recall it
        result = api_client.interact("$recall France")
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Check audit entries
        entries = api_client.get_audit_entries(resource_filter="handler")
        recall_entries = [e for e in entries if "RECALL" in str(e)]
        assert len(recall_entries) > 0, "No RECALL handler entries found"


class TestPonderHandler:
    """Test PONDER handler functionality."""
    
    def test_ponder_single_question(self, api_client):
        """Test pondering a single question."""
        result = api_client.interact("$ponder What is the meaning of life?")
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Check audit entries
        entries = api_client.get_audit_entries(resource_filter="handler")
        ponder_entries = [e for e in entries if "PONDER" in str(e)]
        assert len(ponder_entries) > 0, "No PONDER handler entries found"
        
    def test_ponder_multiple_questions(self, api_client):
        """Test pondering multiple questions."""
        result = api_client.interact("$ponder What should I do next?; How can I be helpful?; Is this ethical?")
        assert "data" in result
        
        api_client.wait_for_processing()


class TestObserveHandler:
    """Test OBSERVE handler functionality."""
    
    def test_observe_channel(self, api_client):
        """Test observing a channel."""
        result = api_client.interact("$observe api_test true")
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Check audit entries
        entries = api_client.get_audit_entries(resource_filter="handler")
        observe_entries = [e for e in entries if "OBSERVE" in str(e)]
        assert len(observe_entries) > 0, "No OBSERVE handler entries found"


class TestToolHandler:
    """Test TOOL handler functionality."""
    
    def test_tool_curl(self, api_client):
        """Test using the curl tool."""
        result = api_client.interact('$tool curl {"url": "http://example.com"}')
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Check audit entries
        entries = api_client.get_audit_entries(resource_filter="handler")
        tool_entries = [e for e in entries if "TOOL" in str(e)]
        assert len(tool_entries) > 0, "No TOOL handler entries found"
        
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
        
        api_client.wait_for_processing()
        
        # Check audit entries
        entries = api_client.get_audit_entries(resource_filter="handler")
        defer_entries = [e for e in entries if "DEFER" in str(e)]
        assert len(defer_entries) > 0, "No DEFER handler entries found"


class TestRejectHandler:
    """Test REJECT handler functionality."""
    
    def test_reject_with_reason(self, api_client):
        """Test rejecting with a reason."""
        result = api_client.interact("$reject This request violates ethical guidelines")
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Check audit entries
        entries = api_client.get_audit_entries(resource_filter="handler")
        reject_entries = [e for e in entries if "REJECT" in str(e)]
        assert len(reject_entries) > 0, "No REJECT handler entries found"


class TestForgetHandler:
    """Test FORGET handler functionality."""
    
    def test_forget_memory(self, api_client):
        """Test forgetting a memory."""
        # First memorize something
        api_client.interact("$memorize Test memory to forget")
        api_client.wait_for_processing()
        
        # Then forget it
        result = api_client.interact("$forget test_memory_to User requested deletion")
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Check audit entries
        entries = api_client.get_audit_entries(resource_filter="handler")
        forget_entries = [e for e in entries if "FORGET" in str(e)]
        assert len(forget_entries) > 0, "No FORGET handler entries found"


class TestTaskCompleteHandler:
    """Test TASK_COMPLETE handler functionality."""
    
    def test_task_complete(self, api_client):
        """Test completing a task."""
        result = api_client.interact("$task_complete")
        assert "data" in result
        
        api_client.wait_for_processing()
        
        # Check audit entries
        entries = api_client.get_audit_entries(resource_filter="handler")
        complete_entries = [e for e in entries if "TASK_COMPLETE" in str(e)]
        assert len(complete_entries) > 0, "No TASK_COMPLETE handler entries found"


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
            api_client.wait_for_processing(5)
            
        # Recall specific information
        result = api_client.interact("$recall programming")
        assert "data" in result
        api_client.wait_for_processing()
        
        # Verify we got some handler activity
        entries = api_client.get_audit_entries(limit=20)
        handler_entries = [e for e in entries if "handler" in e.get("resource", "")]
        assert len(handler_entries) >= 4, f"Expected at least 4 handler entries, got {len(handler_entries)}"
        
    def test_ponder_and_speak_flow(self, api_client):
        """Test pondering followed by speaking."""
        # Ponder questions
        api_client.interact("$ponder What insights can I share?; How can I be helpful?")
        api_client.wait_for_processing()
        
        # Speak response
        api_client.interact("$speak Based on my pondering, I can help by providing information")
        api_client.wait_for_processing()
        
        # Check both handlers were used
        entries = api_client.get_audit_entries(limit=10)
        handler_types = set()
        for entry in entries:
            if "handler" in entry.get("resource", ""):
                details = entry.get("details", {})
                if "handler_type" in details:
                    handler_types.add(details["handler_type"])
                    
        assert "PONDER" in handler_types or "ponder" in str(entries).lower()
        assert "SPEAK" in handler_types or "speak" in str(entries).lower()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])