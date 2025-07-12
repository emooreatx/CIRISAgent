#!/usr/bin/env python3
"""Analyze mypy errors and categorize them for bulk fixes."""

import subprocess
import re
from collections import defaultdict
from typing import Dict, List, Tuple

def get_mypy_errors() -> List[str]:
    """Run mypy and get all error lines."""
    result = subprocess.run(
        ["mypy", "ciris_engine/", "2>&1"],
        capture_output=True,
        text=True,
        shell=True
    )
    return result.stdout.strip().split('\n')

def parse_errors(lines: List[str]) -> Dict[str, List[Tuple[str, int, str]]]:
    """Parse mypy output and categorize errors."""
    errors_by_type = defaultdict(list)
    error_pattern = re.compile(r'^(ciris_engine/[^:]+):(\d+):\d+: error: (.+?)(?:\s+\[.*\])?$')
    
    for line in lines:
        match = error_pattern.match(line)
        if match:
            file_path, line_num, error_msg = match.groups()
            
            # Categorize by error type
            if "Statement is unreachable" in error_msg:
                error_type = "unreachable"
            elif "Item" in error_msg and "has no attribute" in error_msg:
                error_type = "item_no_attr"
            elif "Argument" in error_msg and "to" in error_msg:
                error_type = "argument_type"
            elif "Missing named argument" in error_msg:
                error_type = "missing_arg"
            elif "Incompatible types in assignment" in error_msg:
                error_type = "incompatible_assignment"
            elif "Incompatible return value type" in error_msg:
                error_type = "incompatible_return"
            elif "Unexpected keyword argument" in error_msg:
                error_type = "unexpected_kwarg"
            elif "Need type annotation" in error_msg:
                error_type = "need_annotation"
            elif "Function is missing a type annotation" in error_msg:
                error_type = "missing_func_annotation"
            elif "has no attribute" in error_msg:
                error_type = "no_attribute"
            elif "Value of type" in error_msg:
                error_type = "value_type"
            elif "Name" in error_msg and "already defined" in error_msg:
                error_type = "name_redef"
            else:
                error_type = "other"
            
            errors_by_type[error_type].append((file_path, int(line_num), error_msg))
    
    return errors_by_type

def main():
    print("Analyzing mypy errors...")
    lines = get_mypy_errors()
    errors = parse_errors(lines)
    
    print(f"\nTotal unique errors: {sum(len(v) for v in errors.values())}")
    print("\nErrors by category:")
    for error_type, error_list in sorted(errors.items(), key=lambda x: -len(x[1])):
        print(f"\n{error_type}: {len(error_list)} errors")
        # Show first 3 examples
        for i, (file, line, msg) in enumerate(error_list[:3]):
            print(f"  {file}:{line} - {msg}")
        if len(error_list) > 3:
            print(f"  ... and {len(error_list) - 3} more")

if __name__ == "__main__":
    main()