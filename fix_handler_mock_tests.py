#!/usr/bin/env python3
"""
Fix handler tests that are expecting mock calls
"""

import re

def fix_handler_tests():
    """Fix handler tests that need updates for bus_manager"""
    
    # Fix test_speak_handler.py - update mock assertions
    test_file = 'tests/ciris_engine/action_handlers/test_speak_handler.py'
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Update the assertion to check bus_manager.communication.send_message
    content = re.sub(
        r'mock_sink\.send_message\.assert_awaited_once_with\(([^)]+)\)',
        r'mock_sink.communication.send_message.assert_awaited_once_with(\1)',
        content
    )
    
    with open(test_file, 'w') as f:
        f.write(content)
    print(f"Fixed {test_file}")
    
    # Fix test_reject_handler - similar issue
    test_file = 'tests/ciris_engine/action_handlers/test_remaining_handlers.py'
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Update send_message assertions
    content = re.sub(
        r'mock_sink\.send_message\.assert_awaited_once_with\(([^)]+)\)',
        r'mock_sink.communication.send_message.assert_awaited_once_with(\1)',
        content
    )
    
    # Fix forget handler assertions
    content = re.sub(
        r'mock_sink\.forget\.assert_awaited_once_with\(([^)]+)\)',
        r'mock_sink.memory.forget.assert_awaited_once_with(\1)',
        content
    )
    
    # Fix recall handler assertions  
    content = re.sub(
        r'mock_sink\.recall\.assert_awaited_once_with\(([^)]+)\)',
        r'mock_sink.memory.recall.assert_awaited_once_with(\1)',
        content
    )
    
    with open(test_file, 'w') as f:
        f.write(content)
    print(f"Fixed {test_file}")

if __name__ == "__main__":
    fix_handler_tests()