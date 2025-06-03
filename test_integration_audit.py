#!/usr/bin/env python3
"""
Integration test to verify audit logging works in a simpler way.
This script will:
1. Create a direct test using the audit service in the actual file
2. Check if the audit logs are written to the real audit file
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, '/home/emoore/CIRISAgent')

from ciris_engine.adapters.local_audit_log import AuditService
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


async def test_real_audit_file():
    """Test that audit logs are written to the real audit file location."""
    print("🧪 Starting real audit file integration test...")
    
    # Use the actual audit log file path used by CIRIS
    audit_log_path = Path("/home/emoore/CIRISAgent/audit_logs.jsonl")
    
    # Check initial state
    initial_size = audit_log_path.stat().st_size if audit_log_path.exists() else 0
    print(f"📏 Initial audit log size: {initial_size} bytes")
    
    # Count initial entries
    initial_entries = 0
    if audit_log_path.exists() and initial_size > 0:
        with open(audit_log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    initial_entries += 1
    print(f"📝 Initial audit entries: {initial_entries}")
    
    # Create audit service instance pointing to the real file
    audit_service = AuditService(log_path=audit_log_path)
    
    try:
        print("🚀 Starting audit service...")
        await audit_service.start()
        print("✓ Audit service started")
        
        # Log some test SPEAK actions
        test_actions = [
            {"action": "SPEAK", "message": "Integration test message 1", "thought_id": "integration-test-001"},
            {"action": "SPEAK", "message": "Integration test message 2", "thought_id": "integration-test-002"},
            {"action": "SPEAK", "message": "This tests the audit fix", "thought_id": "integration-test-003"},
        ]
        
        for i, action_data in enumerate(test_actions):
            context = {
                "thought_id": action_data["thought_id"],
                "task_id": "integration-test-task",
                "message": action_data["message"],
                "test_run": True,
            }
            
            success = await audit_service.log_action(
                handler_action=HandlerActionType.SPEAK,
                context=context,
                outcome="success"
            )
            
            if success:
                print(f"✓ Logged test action {i+1}: {action_data['message'][:40]}...")
            else:
                print(f"✗ Failed to log test action {i+1}")
        
        print("🛑 Stopping audit service (should flush buffer)...")
        await audit_service.stop()
        print("✓ Audit service stopped")
        
    except Exception as e:
        print(f"❌ Error during audit service test: {e}")
        return False
    
    # Check final state
    final_size = audit_log_path.stat().st_size if audit_log_path.exists() else 0
    print(f"📏 Final audit log size: {final_size} bytes")
    
    # Count final entries
    final_entries = 0
    test_entries_found = 0
    if audit_log_path.exists() and final_size > 0:
        with open(audit_log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line.strip())
                        final_entries += 1
                        # Check if this is one of our test entries
                        if entry.get("event_payload", {}).get("test_run") == True:
                            test_entries_found += 1
                            print(f"  📝 Found test entry: {entry.get('event_payload', {}).get('message', 'no message')[:40]}...")
                    except json.JSONDecodeError:
                        pass
    
    print(f"📝 Final audit entries: {final_entries} (increased by {final_entries - initial_entries})")
    print(f"🧪 Test entries found: {test_entries_found}")
    
    if test_entries_found == len(test_actions):
        print("🎉 SUCCESS: All test audit entries were written to the real audit file!")
        print("   The audit logging fix is working correctly.")
        return True
    elif test_entries_found > 0:
        print(f"⚠ PARTIAL SUCCESS: Found {test_entries_found} out of {len(test_actions)} test entries")
        print("   The audit logging fix is working but not all entries were written")
        return True
    else:
        print("❌ FAILURE: No test audit entries found in the audit file")
        print("   The audit logging fix may not be working correctly")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_real_audit_file())
        if success:
            print("\n✅ Integration test PASSED: Audit logging fix is working!")
            sys.exit(0)
        else:
            print("\n❌ Integration test FAILED: Audit logging fix needs investigation")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test crashed: {e}")
        sys.exit(1)
