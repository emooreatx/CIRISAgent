#!/usr/bin/env python3
"""
Simple test for mock LLM handlers through API.
Tests the correct command formats.
"""

import requests
import time
import json

class TestMockLLMHandlers:
    def __init__(self):
        self.base_url = "http://localhost:8080"
        self.token = None
        self.headers = {}
        
    def login(self):
        """Login and get token"""
        resp = requests.post(
            f"{self.base_url}/v1/auth/login",
            json={"username": "admin", "password": "ciris_admin_password"}
        )
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            print("✅ Login successful")
            return True
        print(f"❌ Login failed: {resp.status_code}")
        return False
        
    def interact(self, message, channel_id="api_test"):
        """Send message to agent"""
        resp = requests.post(
            f"{self.base_url}/v1/agent/interact",
            json={"message": message, "channel_id": channel_id},
            headers=self.headers
        )
        return resp.json() if resp.status_code == 200 else {"error": resp.text}
        
    def test_speak(self):
        """Test SPEAK handler"""
        print("\n🧪 Testing SPEAK handler...")
        result = self.interact("$speak Hello from test!")
        if "data" in result and result["data"].get("message_id"):
            print(f"✅ SPEAK: Got message_id {result['data']['message_id']}")
            return True
        print(f"❌ SPEAK failed: {result}")
        return False
        
    def test_memorize(self):
        """Test MEMORIZE handler"""
        print("\n🧪 Testing MEMORIZE handler...")
        result = self.interact("$memorize test_data CONCEPT LOCAL")
        if "data" in result and result["data"].get("message_id"):
            print(f"✅ MEMORIZE: Got message_id {result['data']['message_id']}")
            return True
        print(f"❌ MEMORIZE failed: {result}")
        return False
        
    def test_recall(self):
        """Test RECALL handler"""
        print("\n🧪 Testing RECALL handler...")
        # First memorize something
        self.interact("$memorize recall_test CONCEPT LOCAL")
        time.sleep(2)
        
        # Then try to recall it
        result = self.interact("$recall recall_test")
        if "data" in result and result["data"].get("message_id"):
            print(f"✅ RECALL: Got message_id {result['data']['message_id']}")
            return True
        print(f"❌ RECALL failed: {result}")
        return False
        
    def test_ponder(self):
        """Test PONDER handler"""
        print("\n🧪 Testing PONDER handler...")
        result = self.interact("$ponder What is the meaning of life?")
        if "data" in result and result["data"].get("message_id"):
            print(f"✅ PONDER: Got message_id {result['data']['message_id']}")
            return True
        print(f"❌ PONDER failed: {result}")
        return False
        
    def test_tool(self):
        """Test TOOL handler"""
        print("\n🧪 Testing TOOL handler...")
        result = self.interact("$tool list_tools")
        if "data" in result and result["data"].get("message_id"):
            print(f"✅ TOOL: Got message_id {result['data']['message_id']}")
            return True
        print(f"❌ TOOL failed: {result}")
        return False
        
    def test_observe(self):
        """Test OBSERVE handler"""
        print("\n🧪 Testing OBSERVE handler...")
        result = self.interact("$observe api_test")
        if "data" in result and result["data"].get("message_id"):
            print(f"✅ OBSERVE: Got message_id {result['data']['message_id']}")
            return True
        print(f"❌ OBSERVE failed: {result}")
        return False
        
    def test_defer(self):
        """Test DEFER handler"""
        print("\n🧪 Testing DEFER handler...")
        result = self.interact("$defer Need more information")
        if "data" in result and result["data"].get("message_id"):
            print(f"✅ DEFER: Got message_id {result['data']['message_id']}")
            return True
        print(f"❌ DEFER failed: {result}")
        return False
        
    def test_reject(self):
        """Test REJECT handler"""
        print("\n🧪 Testing REJECT handler...")
        result = self.interact("$reject Inappropriate request")
        if "data" in result and result["data"].get("message_id"):
            print(f"✅ REJECT: Got message_id {result['data']['message_id']}")
            return True
        print(f"❌ REJECT failed: {result}")
        return False
        
    def test_task_complete(self):
        """Test TASK_COMPLETE handler"""
        print("\n🧪 Testing TASK_COMPLETE handler...")
        result = self.interact("$task_complete All tests done!")
        if "data" in result and result["data"].get("message_id"):
            print(f"✅ TASK_COMPLETE: Got message_id {result['data']['message_id']}")
            return True
        print(f"❌ TASK_COMPLETE failed: {result}")
        return False
        
    def run_all_tests(self):
        """Run all handler tests"""
        if not self.login():
            return
            
        results = {
            "SPEAK": self.test_speak(),
            "MEMORIZE": self.test_memorize(),
            "RECALL": self.test_recall(),
            "PONDER": self.test_ponder(),
            "TOOL": self.test_tool(),
            "OBSERVE": self.test_observe(),
            "DEFER": self.test_defer(),
            "REJECT": self.test_reject(),
            "TASK_COMPLETE": self.test_task_complete()
        }
        
        print("\n📊 Test Results:")
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for handler, passed in results.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {handler}")
            
        print(f"\n✨ Passed: {passed}/{total}")
        
        # Now test the help fix
        print("\n🧪 Testing $help fix...")
        result = self.interact("$help")
        time.sleep(2)
        # Try another command after help
        result2 = self.interact("$speak Help bug is fixed!")
        if "data" in result2 and result2["data"].get("message_id"):
            print("✅ $help bug is FIXED - subsequent commands work!")
        else:
            print("❌ $help bug still present - subsequent commands fail")

if __name__ == "__main__":
    tester = TestMockLLMHandlers()
    tester.run_all_tests()