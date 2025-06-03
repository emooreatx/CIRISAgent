#!/usr/bin/env python3
"""
Test script to verify the audit service fix.
This script will:
1. Create an audit service instance
2. Log a few SPEAK actions (less than 100 to avoid auto-flush)
3. Stop the service (which should now flush the buffer)
4. Check if entries were written to the audit log file
"""

import asyncio
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# Add the project root to Python path
import sys
sys.path.insert(0, '/home/emoore/CIRISAgent')

from ciris_engine.adapters.local_audit_log import AuditService
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


async def test_audit_fix():
    """Test that audit entries are flushed during service shutdown."""
    
    # Create a temporary directory for the test
    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = Path(temp_dir) / "test_audit.jsonl"
        
        print(f"Creating audit service with log file: {log_path}")
        
        # Create audit service instance
        audit_service = AuditService(log_path=log_path)
        
        # Start the service
        await audit_service.start()
        print("✓ Audit service started")
        
        # Log some SPEAK actions (less than 100 to test the fix)
        test_actions = [
            {"action": "SPEAK", "message": "Hello, world!", "thought_id": "test-001"},
            {"action": "SPEAK", "message": "Testing audit logging", "thought_id": "test-002"},
            {"action": "SPEAK", "message": "This should be flushed on shutdown", "thought_id": "test-003"},
        ]
        
        for i, action_data in enumerate(test_actions):
            context = {
                "thought_id": action_data["thought_id"],
                "task_id": "test-task-123",
                "message": action_data["message"],
            }
            
            success = await audit_service.log_action(
                handler_action=HandlerActionType.SPEAK,
                context=context,
                outcome="success"
            )
            
            if success:
                print(f"✓ Logged action {i+1}: {action_data['message'][:30]}...")
            else:
                print(f"✗ Failed to log action {i+1}")
        
        # Check if file exists before stopping (should not exist yet due to buffering)
        if log_path.exists():
            print(f"⚠ Log file exists before stop (unexpected, size: {log_path.stat().st_size} bytes)")
        else:
            print("✓ Log file doesn't exist yet (expected due to buffering)")
        
        # Stop the service - this should flush the buffer
        print("Stopping audit service (should flush buffer)...")
        await audit_service.stop()
        print("✓ Audit service stopped")
        
        # Check if the file was created and contains our entries
        if log_path.exists():
            print(f"✓ Log file created: {log_path}")
            
            # Read and verify the contents
            entries = []
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entries.append(entry)
                    except json.JSONDecodeError as e:
                        print(f"✗ Failed to parse JSON line: {e}")
            
            print(f"✓ Found {len(entries)} entries in log file")
            
            # Verify we have the expected number of entries
            if len(entries) == len(test_actions):
                print("✓ All logged actions were successfully written to disk")
                
                # Verify entry content
                for i, entry in enumerate(entries):
                    expected_message = test_actions[i]["message"]
                    if "message" in entry.get("event_payload", {}):
                        actual_message = entry["event_payload"]["message"]
                        if actual_message == expected_message:
                            print(f"✓ Entry {i+1} content verified: {actual_message[:30]}...")
                        else:
                            print(f"✗ Entry {i+1} content mismatch")
                    else:
                        print(f"⚠ Entry {i+1} missing expected message field")
                
                print("\n🎉 TEST PASSED: Audit service fix is working correctly!")
                print("   SPEAK operations are now being flushed to disk during shutdown.")
                
            else:
                print(f"✗ Expected {len(test_actions)} entries, but found {len(entries)}")
                print("   TEST FAILED: Not all entries were written to disk")
        else:
            print("✗ Log file was not created")
            print("   TEST FAILED: Buffer was not flushed during shutdown")


if __name__ == "__main__":
    asyncio.run(test_audit_fix())
