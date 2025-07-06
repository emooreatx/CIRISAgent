#!/usr/bin/env python3
"""
Comprehensive test to identify missing values in SDK/API responses.
This script tests all SDK methods against a live API and reports any missing required fields.
"""

import asyncio
import json
import traceback
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Import the SDK
import sys
sys.path.append('/home/emoore/CIRISAgent')
from ciris_sdk import CIRISClient
from ciris_sdk.exceptions import CIRISValidationError, CIRISAPIError, CIRISNotFoundError


@dataclass
class TestResult:
    """Result of a single test."""
    method_name: str
    endpoint: str
    success: bool
    error: Optional[str] = None
    missing_fields: List[str] = None
    response_data: Any = None
    traceback: Optional[str] = None


class SDKTester:
    """Comprehensive SDK tester."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.client = None
        self.results: List[TestResult] = []
        
    async def setup(self):
        """Setup - create client and login to get auth token."""
        try:
            self.client = CIRISClient(base_url=self.base_url)
            await self.client.__aenter__()  # Start the client
            await self.client.auth.login("admin", "ciris_admin_password")
            print("✓ Successfully logged in")
            return True
        except Exception as e:
            print(f"✗ Failed to login: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def cleanup(self):
        """Cleanup - close the client."""
        if self.client:
            await self.client.__aexit__(None, None, None)
    
    async def test_auth_endpoints(self):
        """Test authentication endpoints."""
        print("\n=== Testing Auth Endpoints ===")
        
        # Test current user
        result = await self._test_method(
            "auth.get_current_user",
            self.client.auth.get_current_user,
            required_fields=["username", "role", "permissions"]
        )
        
        # Test refresh token
        result = await self._test_method(
            "auth.refresh_token",
            self.client.auth.refresh_token,
            required_fields=["access_token", "token_type"]
        )
    
    async def test_agent_endpoints(self):
        """Test agent endpoints."""
        print("\n=== Testing Agent Endpoints ===")
        
        # Test status
        await self._test_method(
            "agent.get_status",
            self.client.agent.get_status,
            required_fields=["state", "is_processing", "last_activity"]
        )
        
        # Test identity
        await self._test_method(
            "agent.get_identity",
            self.client.agent.get_identity,
            required_fields=["name", "version", "capabilities"]
        )
        
        # Test interact
        await self._test_method(
            "agent.interact",
            self.client.agent.interact,
            args=["Hello from SDK test", "test_channel"],
            required_fields=["response", "thought_id"]
        )
        
        # Test history
        await self._test_method(
            "agent.get_history",
            self.client.agent.get_history,
            kwargs={"channel_id": "test_channel", "limit": 10},
            required_fields=["messages", "total_count"]
        )
    
    async def test_system_endpoints(self):
        """Test system management endpoints."""
        print("\n=== Testing System Endpoints ===")
        
        # Test health
        await self._test_method(
            "system.get_health",
            self.client.system.get_health,
            required_fields=["status", "uptime", "version"]
        )
        
        # Test resources
        await self._test_method(
            "system.get_resources", 
            self.client.system.get_resources,
            required_fields=["cpu_percent", "memory", "disk"]
        )
        
        # Test time
        await self._test_method(
            "system.get_time",
            self.client.system.get_time,
            required_fields=["current_time", "timezone", "uptime"]
        )
        
        # Test processors
        await self._test_method(
            "system.get_processors",
            self.client.system.get_processors,
            required_fields=None  # This returns a list
        )
        
        # Test runtime state
        await self._test_method(
            "system.get_runtime_state",
            self.client.system.get_runtime_state,
            required_fields=["processor_state", "is_paused", "queue_size"]
        )
        
        # Test queue status
        await self._test_method(
            "system.get_processing_queue_status",
            self.client.system.get_processing_queue_status,
            required_fields=["processor_name", "queue_size", "processing_status"]
        )
        
        # Test service health details
        await self._test_method(
            "system.get_service_health_details",
            self.client.system.get_service_health_details,
            required_fields=["overall_health", "healthy_services", "unhealthy_services", "service_details"]
        )
        
        # Test adapters
        await self._test_method(
            "system.list_adapters",
            self.client.system.list_adapters,
            required_fields=None  # Returns a list
        )
    
    async def test_memory_endpoints(self):
        """Test memory endpoints."""
        print("\n=== Testing Memory Endpoints ===")
        
        # Test create memory
        test_memory = {
            "content": "Test memory from SDK",
            "memory_type": "observation",
            "tags": ["test", "sdk"],
            "metadata": {"source": "sdk_test"}
        }
        
        create_result = await self._test_method(
            "memory.create",
            self.client.memory.create,
            args=[test_memory],
            required_fields=["id", "content", "created_at"]
        )
        
        if create_result.success and create_result.response_data:
            memory_id = create_result.response_data.get("id")
            
            # Test get memory
            await self._test_method(
                "memory.get",
                self.client.memory.get,
                args=[memory_id],
                required_fields=["id", "content", "memory_type", "created_at"]
            )
            
            # Test update memory
            await self._test_method(
                "memory.update",
                self.client.memory.update,
                args=[memory_id, {"content": "Updated test memory"}],
                required_fields=["id", "content", "updated_at"]
            )
            
            # Test delete memory
            await self._test_method(
                "memory.delete",
                self.client.memory.delete,
                args=[memory_id],
                required_fields=["success"]
            )
        
        # Test query memories
        await self._test_method(
            "memory.query",
            self.client.memory.query,
            kwargs={"query": "test", "limit": 10},
            required_fields=["results", "total_count"]
        )
        
        # Test timeline
        await self._test_method(
            "memory.get_timeline",
            self.client.memory.get_timeline,
            kwargs={"hours": 24},
            required_fields=["events", "start_time", "end_time"]
        )
    
    async def test_telemetry_endpoints(self):
        """Test telemetry endpoints."""
        print("\n=== Testing Telemetry Endpoints ===")
        
        # Test metrics
        await self._test_method(
            "telemetry.get_metrics",
            self.client.telemetry.get_metrics,
            kwargs={"hours": 1},
            required_fields=["metrics", "start_time", "end_time"]
        )
        
        # Test logs
        await self._test_method(
            "telemetry.get_logs",
            self.client.telemetry.get_logs,
            kwargs={"limit": 10, "level": "INFO"},
            required_fields=["logs", "total_count"]
        )
        
        # Test traces
        await self._test_method(
            "telemetry.get_traces",
            self.client.telemetry.get_traces,
            kwargs={"limit": 10},
            required_fields=["traces", "total_count"]
        )
        
        # Test resources
        await self._test_method(
            "telemetry.get_resource_metrics",
            self.client.telemetry.get_resource_metrics,
            required_fields=["cpu", "memory", "disk", "timestamp"]
        )
    
    async def test_config_endpoints(self):
        """Test configuration endpoints."""
        print("\n=== Testing Config Endpoints ===")
        
        # Test get all config
        await self._test_method(
            "config.get_all",
            self.client.config.get_all,
            required_fields=["configs", "version"]
        )
        
        # Test get specific config
        await self._test_method(
            "config.get",
            self.client.config.get,
            args=["agent"],
            required_fields=["key", "value", "updated_at"]
        )
    
    async def test_audit_endpoints(self):
        """Test audit endpoints."""
        print("\n=== Testing Audit Endpoints ===")
        
        # Test get audit logs
        await self._test_method(
            "audit.get_logs",
            self.client.audit.get_logs,
            kwargs={"limit": 10},
            required_fields=["entries", "total_count"]
        )
        
        # Test search
        await self._test_method(
            "audit.search",
            self.client.audit.search,
            kwargs={"query": "login", "limit": 10},
            required_fields=["results", "total_count"]
        )
        
        # Test verify (might not have entries to verify)
        # Skip this as it requires a valid entry hash
    
    async def test_wa_endpoints(self):
        """Test Wise Authority endpoints."""
        print("\n=== Testing Wise Authority Endpoints ===")
        
        # Test get deferrals
        await self._test_method(
            "wa.get_deferrals",
            self.client.wa.get_deferrals,
            kwargs={"status": "pending"},
            required_fields=["deferrals", "total_count"]
        )
        
        # Test get permissions
        await self._test_method(
            "wa.get_permissions",
            self.client.wa.get_permissions,
            required_fields=["permissions", "role"]
        )
    
    async def _test_method(
        self,
        method_name: str,
        method,
        args: List = None,
        kwargs: Dict = None,
        required_fields: Optional[List[str]] = None
    ) -> TestResult:
        """Test a single SDK method."""
        args = args or []
        kwargs = kwargs or {}
        
        # Extract endpoint info
        if hasattr(method, "__self__") and hasattr(method.__self__, "_client"):
            # This is a resource method
            resource = method.__self__
            endpoint = f"{resource._client._base_url}/{getattr(resource, '_base_path', 'unknown')}"
        else:
            endpoint = "unknown"
        
        print(f"\nTesting {method_name}...")
        
        try:
            # Call the method
            result = await method(*args, **kwargs)
            
            # Check for missing required fields
            missing_fields = []
            if required_fields and isinstance(result, dict):
                for field in required_fields:
                    if field not in result:
                        missing_fields.append(field)
            
            if missing_fields:
                test_result = TestResult(
                    method_name=method_name,
                    endpoint=endpoint,
                    success=False,
                    error=f"Missing required fields: {missing_fields}",
                    missing_fields=missing_fields,
                    response_data=result
                )
                print(f"  ✗ Missing fields: {missing_fields}")
            else:
                test_result = TestResult(
                    method_name=method_name,
                    endpoint=endpoint,
                    success=True,
                    response_data=result
                )
                print(f"  ✓ Success")
                
        except CIRISValidationError as e:
            test_result = TestResult(
                method_name=method_name,
                endpoint=endpoint,
                success=False,
                error=f"Validation error: {str(e)}",
                traceback=traceback.format_exc()
            )
            print(f"  ✗ Validation error: {e}")
            
        except CIRISAPIError as e:
            test_result = TestResult(
                method_name=method_name,
                endpoint=endpoint,
                success=False,
                error=f"API error: {str(e)}",
                traceback=traceback.format_exc()
            )
            print(f"  ✗ API error: {e}")
            
        except Exception as e:
            test_result = TestResult(
                method_name=method_name,
                endpoint=endpoint,
                success=False,
                error=f"Unexpected error: {type(e).__name__}: {str(e)}",
                traceback=traceback.format_exc()
            )
            print(f"  ✗ Unexpected error: {type(e).__name__}: {e}")
        
        self.results.append(test_result)
        return test_result
    
    async def run_all_tests(self):
        """Run all tests."""
        if not await self.setup():
            return
        
        try:
            # Run all test categories
            await self.test_auth_endpoints()
            await self.test_agent_endpoints()
            await self.test_system_endpoints()
            await self.test_memory_endpoints()
            await self.test_telemetry_endpoints()
            await self.test_config_endpoints()
            await self.test_audit_endpoints()
            await self.test_wa_endpoints()
        finally:
            # Always cleanup
            await self.cleanup()
            
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate a detailed report of test results."""
        print("\n" + "="*80)
        print("SDK/API TEST RESULTS SUMMARY")
        print("="*80)
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - successful_tests
        
        print(f"\nTotal tests: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {failed_tests}")
        
        if failed_tests > 0:
            print("\n" + "-"*80)
            print("FAILED TESTS DETAILS")
            print("-"*80)
            
            # Group failures by error type
            validation_errors = []
            missing_field_errors = []
            api_errors = []
            other_errors = []
            
            for result in self.results:
                if not result.success:
                    if result.missing_fields:
                        missing_field_errors.append(result)
                    elif "Validation error" in result.error:
                        validation_errors.append(result)
                    elif "API error" in result.error:
                        api_errors.append(result)
                    else:
                        other_errors.append(result)
            
            # Report missing fields
            if missing_field_errors:
                print(f"\nMISSING FIELDS ({len(missing_field_errors)} issues):")
                for result in missing_field_errors:
                    print(f"\n  • {result.method_name}")
                    print(f"    Missing: {', '.join(result.missing_fields)}")
                    if result.response_data:
                        print(f"    Actual fields: {list(result.response_data.keys())}")
            
            # Report validation errors
            if validation_errors:
                print(f"\nVALIDATION ERRORS ({len(validation_errors)} issues):")
                for result in validation_errors:
                    print(f"\n  • {result.method_name}")
                    print(f"    Error: {result.error}")
            
            # Report API errors
            if api_errors:
                print(f"\nAPI ERRORS ({len(api_errors)} issues):")
                for result in api_errors:
                    print(f"\n  • {result.method_name}")
                    print(f"    Error: {result.error}")
            
            # Report other errors
            if other_errors:
                print(f"\nOTHER ERRORS ({len(other_errors)} issues):")
                for result in other_errors:
                    print(f"\n  • {result.method_name}")
                    print(f"    Error: {result.error}")
                    if result.traceback:
                        print(f"    Traceback:\n{result.traceback}")
        
        # Save detailed results to file
        with open("sdk_test_results.json", "w") as f:
            json.dump(
                [
                    {
                        "method": r.method_name,
                        "endpoint": r.endpoint,
                        "success": r.success,
                        "error": r.error,
                        "missing_fields": r.missing_fields,
                        "response_data": str(r.response_data) if r.response_data else None
                    }
                    for r in self.results
                ],
                f,
                indent=2
            )
        print(f"\n\nDetailed results saved to sdk_test_results.json")


async def main():
    """Main entry point."""
    tester = SDKTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())