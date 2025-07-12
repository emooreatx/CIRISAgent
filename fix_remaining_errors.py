#!/usr/bin/env python3
"""Systematically fix remaining mypy errors."""

import re
from collections import defaultdict
from typing import Dict, List, Tuple

def analyze_errors():
    """Read and categorize mypy errors."""
    errors_by_file = defaultdict(list)
    
    with open('mypy_errors.txt', 'r') as f:
        for line in f:
            match = re.match(r'^(ciris_engine/[^:]+):(\d+):\d+: error: (.+?)(?:\s+\[([^\]]+)\])?$', line.strip())
            if match:
                file_path, line_num, error_msg, error_code = match.groups()
                errors_by_file[file_path].append({
                    'line': int(line_num),
                    'msg': error_msg,
                    'code': error_code or 'unknown'
                })
    
    # Sort files by error count
    sorted_files = sorted(errors_by_file.items(), key=lambda x: -len(x[1]))
    
    print("Files with most errors:")
    for file_path, errors in sorted_files[:10]:
        print(f"\n{file_path}: {len(errors)} errors")
        # Group by error type
        by_type = defaultdict(list)
        for err in errors:
            by_type[err['code']].append(err)
        
        for code, err_list in sorted(by_type.items(), key=lambda x: -len(x[1])):
            print(f"  {code}: {len(err_list)} errors")
            if len(err_list) <= 3:
                for err in err_list:
                    print(f"    Line {err['line']}: {err['msg']}")

if __name__ == "__main__":
    analyze_errors()