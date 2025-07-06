#!/usr/bin/env python3
"""
Comprehensive SDK test to find all missing values and API/SDK mismatches.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

import sys
sys.path.append('/home/emoore/CIRISAgent')
from ciris_sdk import CIRISClient, GraphNode, MemoryScope


@dataclass
class IssueReport:
    """Report of an SDK/API issue."""
    endpoint: str
    method: str
    issue_type: str  # "missing_field", "wrong_type", "method_error", "api_error"
    details: str
    actual_response: Optional[Any] = None
    expected_fields: Optional[List[str]] = None
    actual_fields: Optional[List[str]] = None


@dataclass
class TestSummary:
    """Summary of all tests."""
    total_tests: int = 0
    successful: int = 0
    failed: int = 0
    issues: List[IssueReport] = field(default_factory=list)


class SDKComprehensiveTester:
    """Comprehensive SDK tester."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.client = None
        self.summary = TestSummary()
        
    async def setup(self):
        """Setup - create client and authenticate."""
        self.client = CIRISClient(base_url=self.base_url)
        await self.client.__aenter__()
        
        # Login and set token
        login_response = await self.client.auth.login("admin", "ciris_admin_password")
        self.client.set_api_key(login_response.access_token)
        print("✓ Authentication successful")
        
    async def cleanup(self):
        """Cleanup - close client."""
        if self.client:
            await self.client.__aexit__(None, None, None)
    
    async def test_method(
        self,
        endpoint: str,
        method_name: str,
        method_func,
        args: List = None,
        kwargs: Dict = None,
        expected_fields: Optional[List[str]] = None,
        check_response: bool = True
    ):
        """Test a single SDK method and check for missing fields."""
        args = args or []
        kwargs = kwargs or {}
        self.summary.total_tests += 1
        
        print(f"\n  Testing {method_name}...", end=" ")
        
        try:
            result = await method_func(*args, **kwargs)
            
            if check_response and expected_fields and hasattr(result, '__dict__'):
                # Check for missing expected fields
                actual_fields = list(vars(result).keys())
                missing = [f for f in expected_fields if not hasattr(result, f)]
                
                if missing:
                    self.summary.issues.append(IssueReport(
                        endpoint=endpoint,
                        method=method_name,
                        issue_type="missing_field",
                        details=f"Missing fields: {missing}",
                        expected_fields=expected_fields,
                        actual_fields=actual_fields,
                        actual_response=str(result)
                    ))
                    print(f"✗ Missing fields: {missing}")
                else:
                    self.summary.successful += 1
                    print("✓ Success")
            else:
                self.summary.successful += 1
                print("✓ Success")
                
        except Exception as e:
            self.summary.failed += 1
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Categorize the error
            if "validation error" in error_msg.lower():
                issue_type = "validation_error"
            elif "unexpected keyword argument" in error_msg:
                issue_type = "method_signature_mismatch"
            elif "object has no attribute" in error_msg:
                issue_type = "missing_method"
            elif "401" in error_msg:
                issue_type = "auth_error"
            else:
                issue_type = "other_error"
                
            self.summary.issues.append(IssueReport(
                endpoint=endpoint,
                method=method_name,
                issue_type=issue_type,
                details=f"{error_type}: {error_msg}"
            ))
            print(f"✗ {error_type}: {error_msg[:60]}...")
    
    async def run_all_tests(self):
        """Run all SDK tests."""
        await self.setup()
        
        try:
            # Test each resource systematically
            await self.test_auth_resource()
            await self.test_agent_resource()
            await self.test_system_resource()
            await self.test_memory_resource()
            await self.test_telemetry_resource()
            await self.test_config_resource()
            await self.test_audit_resource()
            await self.test_wa_resource()
            
        finally:
            await self.cleanup()
            
        self.generate_report()
    
    async def test_auth_resource(self):
        """Test auth resource methods."""
        print("\n=== Testing Auth Resource ===")
        
        await self.test_method(
            "/v1/auth/me",
            "auth.get_current_user",
            self.client.auth.get_current_user,
            expected_fields=["user_id", "username", "role", "permissions", "created_at"]
        )
        
        await self.test_method(
            "/v1/auth/refresh",
            "auth.refresh_token",
            self.client.auth.refresh_token,
            expected_fields=["access_token", "token_type", "expires_in"]
        )
    
    async def test_agent_resource(self):
        """Test agent resource methods."""
        print("\n=== Testing Agent Resource ===")
        
        await self.test_method(
            "/v1/agent/status",
            "agent.get_status",
            self.client.agent.get_status,
            expected_fields=["agent_id", "name", "cognitive_state", "uptime_seconds", 
                           "messages_processed", "last_activity", "current_task"]
        )
        
        await self.test_method(
            "/v1/agent/identity",
            "agent.get_identity",
            self.client.agent.get_identity,
            expected_fields=["agent_id", "name", "description", "capabilities", "version"]
        )
        
        # Test interact with proper context
        await self.test_method(
            "/v1/agent/interact",
            "agent.interact",
            self.client.agent.interact,
            args=["Test message"],
            kwargs={"context": {"channel_id": "test_channel"}},
            expected_fields=["response", "thought_id", "processing_time_ms", "handler"]
        )
        
        # Test get_history
        await self.test_method(
            "/v1/agent/history",
            "agent.get_history",
            self.client.agent.get_history,
            kwargs={"limit": 5},
            expected_fields=["messages", "total", "has_more"]
        )
    
    async def test_system_resource(self):
        """Test system resource methods."""
        print("\n=== Testing System Resource ===")
        
        await self.test_method(
            "/v1/system/health",
            "system.health",
            self.client.system.health,
            expected_fields=["status", "version", "uptime_seconds", "services", 
                           "initialization_complete", "cognitive_state", "timestamp"]
        )
        
        await self.test_method(
            "/v1/system/resources",
            "system.resources",
            self.client.system.resources,
            expected_fields=["cpu_percent", "memory", "disk", "network", "timestamp"]
        )
        
        await self.test_method(
            "/v1/system/time",
            "system.time",
            self.client.system.time,
            expected_fields=["current_time", "timezone", "uptime_seconds"]
        )
        
        # Runtime control methods
        await self.test_method(
            "/v1/system/runtime/state",
            "system.get_state",
            self.client.system.get_state,
            expected_fields=["processor_state", "is_paused", "queue_size", "active_task"]
        )
    
    async def test_memory_resource(self):
        """Test memory resource methods."""
        print("\n=== Testing Memory Resource ===")
        
        # Test store with proper scope
        test_node = GraphNode(
            id="test_node_comprehensive",
            type="test",
            scope=MemoryScope.LOCAL,  # Add required scope
            attributes={
                "content": "Test from comprehensive SDK test",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        await self.test_method(
            "/v1/memory",
            "memory.store",
            self.client.memory.store,
            args=[test_node],
            expected_fields=["success", "node_id", "message"]
        )
        
        # Test query
        await self.test_method(
            "/v1/memory/query",
            "memory.query",
            self.client.memory.query,
            kwargs={"text": "test", "limit": 5},
            expected_fields=["nodes", "total", "query_time_ms"]
        )
        
        # Test timeline
        await self.test_method(
            "/v1/memory/timeline",
            "memory.get_timeline",
            self.client.memory.get_timeline,
            kwargs={"limit": 10},
            expected_fields=["events", "start_time", "end_time", "total"]
        )
    
    async def test_telemetry_resource(self):
        """Test telemetry resource methods."""
        print("\n=== Testing Telemetry Resource ===")
        
        # Test get metrics (check what params it actually accepts)
        await self.test_method(
            "/v1/telemetry/metrics",
            "telemetry.get_metrics",
            self.client.telemetry.get_metrics,
            expected_fields=["metrics", "start_time", "end_time", "total"]
        )
        
        # Test get logs
        await self.test_method(
            "/v1/telemetry/logs",
            "telemetry.get_logs",
            self.client.telemetry.get_logs,
            kwargs={"limit": 5},
            expected_fields=["logs", "total", "has_more"]
        )
        
        # Test get traces
        await self.test_method(
            "/v1/telemetry/traces",
            "telemetry.get_traces",
            self.client.telemetry.get_traces,
            kwargs={"limit": 5},
            expected_fields=["traces", "total"]
        )
    
    async def test_config_resource(self):
        """Test config resource methods."""
        print("\n=== Testing Config Resource ===")
        
        await self.test_method(
            "/v1/config",
            "config.get_all",
            self.client.config.get_all,
            expected_fields=["configs", "version", "last_updated"]
        )
        
        await self.test_method(
            "/v1/config/agent",
            "config.get",
            self.client.config.get,
            args=["agent"],
            expected_fields=["key", "value", "description", "updated_at"]
        )
    
    async def test_audit_resource(self):
        """Test audit resource methods."""
        print("\n=== Testing Audit Resource ===")
        
        await self.test_method(
            "/v1/audit/entries",
            "audit.get_logs",
            self.client.audit.get_logs,
            kwargs={"limit": 5},
            expected_fields=["entries", "total", "has_more"]
        )
        
        await self.test_method(
            "/v1/audit/search",
            "audit.search",
            self.client.audit.search,
            kwargs={"query": "login", "limit": 5},
            expected_fields=["results", "total", "query_time_ms"]
        )
    
    async def test_wa_resource(self):
        """Test Wise Authority resource methods."""
        print("\n=== Testing Wise Authority Resource ===")
        
        await self.test_method(
            "/v1/wa/deferrals",
            "wa.get_deferrals",
            self.client.wa.get_deferrals,
            kwargs={"status": "pending"},
            expected_fields=["deferrals", "total", "has_more"]
        )
        
        await self.test_method(
            "/v1/wa/permissions",
            "wa.get_permissions",
            self.client.wa.get_permissions,
            expected_fields=["permissions", "role", "user_id"]
        )
    
    def generate_report(self):
        """Generate comprehensive report of issues."""
        print("\n" + "="*80)
        print("SDK/API COMPATIBILITY REPORT")
        print("="*80)
        
        print(f"\nTotal tests: {self.summary.total_tests}")
        print(f"Successful: {self.summary.successful}")
        print(f"Failed: {self.summary.failed}")
        
        if self.summary.issues:
            print(f"\nTotal issues found: {len(self.summary.issues)}")
            
            # Group issues by type
            issues_by_type = {}
            for issue in self.summary.issues:
                if issue.issue_type not in issues_by_type:
                    issues_by_type[issue.issue_type] = []
                issues_by_type[issue.issue_type].append(issue)
            
            # Report each type
            for issue_type, issues in issues_by_type.items():
                print(f"\n### {issue_type.upper().replace('_', ' ')} ({len(issues)} issues)")
                print("-" * 60)
                
                for issue in issues:
                    print(f"\n• {issue.method}")
                    print(f"  Endpoint: {issue.endpoint}")
                    print(f"  Details: {issue.details}")
                    
                    if issue.expected_fields and issue.actual_fields:
                        print(f"  Expected: {issue.expected_fields}")
                        print(f"  Actual: {issue.actual_fields}")
                    
                    if issue.actual_response:
                        print(f"  Response: {issue.actual_response[:100]}...")
        
        # Save detailed report
        report_data = {
            "summary": {
                "total": self.summary.total_tests,
                "successful": self.summary.successful,
                "failed": self.summary.failed
            },
            "issues": [
                {
                    "endpoint": issue.endpoint,
                    "method": issue.method,
                    "type": issue.issue_type,
                    "details": issue.details,
                    "expected_fields": issue.expected_fields,
                    "actual_fields": issue.actual_fields
                }
                for issue in self.summary.issues
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        with open("sdk_compatibility_report.json", "w") as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n\nDetailed report saved to sdk_compatibility_report.json")


async def main():
    """Run comprehensive SDK tests."""
    tester = SDKComprehensiveTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())