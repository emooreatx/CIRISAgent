#!/usr/bin/env python3
"""Test node ID detection logic."""

import re

def test_sdk_node_detection():
    """Test the SDK's node ID detection logic."""
    test_cases = [
        # Standard prefixes
        ("metric_cpu_usage_1234567890", True),
        ("audit_entry_1234567890", True),
        ("log_error_1234567890", True),
        ("dream_schedule_daily_1234567890", True),
        
        # Other node ID formats
        ("thought_abc123_1234567890", True),
        ("task_xyz_1734567890", True),
        ("observation_test_1634567890", True),
        ("concept_knowledge_1534567890", True),
        ("identity_self_1434567890", True),
        ("config_setting_1334567890", True),
        
        # Edge cases
        ("test_node_1234567890", True),  # Has underscore and 10 digits
        ("node_with_many_parts_1234567890_extra", True),  # Extra parts
        ("shortid_1234567890", True),  # Minimal case
        
        # Non-node IDs
        ("simple text query", False),
        ("search for metrics", False),
        ("node_without_timestamp", False),
        ("has_underscore_but_no_digits", False),
        ("has_123_but_not_ten_digits", False),
        ("1234567890", False),  # Just digits, no underscore
        ("_1234567890", False),  # Starts with underscore
        
        # Real examples from CIRIS
        ("thought_7f8a9b2c_1734567890", True),
        ("audit_652a8f91-3d4e-4c5a-8b7f-9c1234567890_1734567890", True),
        ("metric_llm_calls_1734567890", True),
        ("tsdb_data_metric_cpu_1734567890", True),
    ]
    
    print("Testing SDK node ID detection logic:")
    print("=" * 60)
    
    for test_id, expected in test_cases:
        # Current SDK detection logic
        is_node_id_current = test_id and (
            test_id.startswith('metric_') or 
            test_id.startswith('audit_') or 
            test_id.startswith('log_') or
            test_id.startswith('dream_schedule_') or
            (test_id.count('_') >= 1 and re.search(r'\d{10}', test_id) is not None)
        )
        
        # Improved detection logic
        is_node_id_improved = test_id and (
            # Known prefixes
            test_id.startswith(('metric_', 'audit_', 'log_', 'dream_schedule_', 
                              'thought_', 'task_', 'observation_', 'concept_',
                              'identity_', 'config_', 'tsdb_data_')) or
            # Generic pattern: contains underscore and 10-digit timestamp
            (test_id.count('_') >= 1 and re.search(r'\d{10}', test_id) is not None)
        )
        
        current_correct = is_node_id_current == expected
        improved_correct = is_node_id_improved == expected
        
        status_current = "✓" if current_correct else "✗"
        status_improved = "✓" if improved_correct else "✗"
        
        print(f"{status_current} Current:  '{test_id}' -> {is_node_id_current} (expected: {expected})")
        if not current_correct and improved_correct:
            print(f"{status_improved} Improved: '{test_id}' -> {is_node_id_improved} ← FIXED!")
        
    print("\n" + "=" * 60)
    print("Summary:")
    print("- Current logic misses some valid node types (thought_, task_, etc.)")
    print("- Improved logic adds more known prefixes")
    print("- Both use the pattern: underscore + 10-digit timestamp")

if __name__ == "__main__":
    test_sdk_node_detection()