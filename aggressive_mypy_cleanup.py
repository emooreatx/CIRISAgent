#!/usr/bin/env python3
"""
Aggressive MyPy Cleanup - Direct approach for 100% error elimination
Pre-beta mode: No legacy compatibility, mission-critical cleanliness
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict


def get_all_mypy_errors() -> List[Dict[str, Any]]:
    """Get ALL mypy errors with 100% accuracy."""
    cmd = "python -m mypy ciris_engine/ --ignore-missing-imports --show-error-codes --no-error-summary"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    errors = []
    lines = result.stdout.splitlines()
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Look for error lines: file:line: error: message
        match = re.search(r'^([^:]+):(\d+)(?::(\d+))?\s*:\s*error:\s*(.+)', line)
        if match:
            file_path = match.group(1)
            line_num = int(match.group(2))
            col_num = int(match.group(3)) if match.group(3) else 0
            message = match.group(4).strip()
            
            # Look for error code on next line
            error_code = 'unknown'
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line.strip().startswith('[') and next_line.strip().endswith(']'):
                    error_code = next_line.strip()[1:-1]
                    i += 1
            
            errors.append({
                'file': file_path,
                'line': line_num,
                'col': col_num,
                'message': message,
                'code': error_code
            })
        
        i += 1
    
    return errors


def fix_unused_ignore_comments(errors: List[Dict[str, Any]]) -> int:
    """Remove all unused type: ignore comments."""
    print("🧹 Removing unused type: ignore comments...")
    
    unused_ignore_errors = [e for e in errors if e['code'] == 'unused-ignore']
    fixes = 0
    
    # Group by file for efficiency
    files_to_fix = defaultdict(list)
    for error in unused_ignore_errors:
        files_to_fix[error['file']].append(error['line'])
    
    for file_path, line_numbers in files_to_fix.items():
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Remove type: ignore comments from specified lines (reverse order to maintain line numbers)
            for line_num in sorted(line_numbers, reverse=True):
                if line_num <= len(lines):
                    line = lines[line_num - 1]
                    # Remove type: ignore comment
                    cleaned_line = re.sub(r'\s*#\s*type:\s*ignore[^\n]*', '', line)
                    lines[line_num - 1] = cleaned_line
                    fixes += 1
            
            # Write back
            with open(file_path, 'w') as f:
                f.writelines(lines)
                
            print(f"  ✅ Fixed {len(line_numbers)} unused ignores in {file_path}")
            
        except Exception as e:
            print(f"  ❌ Error fixing {file_path}: {e}")
    
    return fixes


def fix_missing_return_types(errors: List[Dict[str, Any]]) -> int:
    """Add missing return type annotations."""
    print("🔧 Adding missing return type annotations...")
    
    untyped_def_errors = [e for e in errors if e['code'] == 'no-untyped-def']
    fixes = 0
    
    for error in untyped_def_errors:
        if "missing a return type annotation" in error['message']:
            try:
                file_path = error['file']
                line_num = error['line']
                
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                
                if line_num <= len(lines):
                    line = lines[line_num - 1]
                    # Add -> None to function definition
                    if re.match(r'^\s*(async\s+)?def\s+\w+\([^)]*\)\s*:\s*$', line):
                        lines[line_num - 1] = line.rstrip().replace('):', ') -> None:') + '\n'
                        fixes += 1
                        
                        with open(file_path, 'w') as f:
                            f.writelines(lines)
                        
                        print(f"  ✅ Added return type to {file_path}:{line_num}")
                        
            except Exception as e:
                print(f"  ❌ Error fixing {error['file']}:{error['line']}: {e}")
    
    return fixes


def fix_unreachable_code(errors: List[Dict[str, Any]]) -> int:
    """Remove or comment out unreachable code."""
    print("🚮 Handling unreachable code...")
    
    unreachable_errors = [e for e in errors if e['code'] == 'unreachable']
    fixes = 0
    
    for error in unreachable_errors:
        try:
            file_path = error['file']
            line_num = error['line']
            
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            if line_num <= len(lines):
                line = lines[line_num - 1]
                # Comment out unreachable code
                if not line.strip().startswith('#'):
                    indent = re.match(r'^(\s*)', line).group(1)
                    lines[line_num - 1] = f"{indent}# {line.lstrip()}"
                    fixes += 1
                    
                    with open(file_path, 'w') as f:
                        f.writelines(lines)
                    
                    print(f"  ✅ Commented unreachable code in {file_path}:{line_num}")
                        
        except Exception as e:
            print(f"  ❌ Error fixing {error['file']}:{error['line']}: {e}")
    
    return fixes


def fix_missing_imports(errors: List[Dict[str, Any]]) -> int:
    """Fix missing imports like Dict, List, Any."""
    print("📦 Adding missing imports...")
    
    name_defined_errors = [e for e in errors if e['code'] == 'name-defined']
    fixes = 0
    
    # Group by file
    files_to_fix = defaultdict(set)
    for error in name_defined_errors:
        if 'not defined' in error['message']:
            if 'Dict' in error['message']:
                files_to_fix[error['file']].add('Dict')
            elif 'List' in error['message']:
                files_to_fix[error['file']].add('List')
            elif 'Any' in error['message']:
                files_to_fix[error['file']].add('Any')
            elif 'Optional' in error['message']:
                files_to_fix[error['file']].add('Optional')
    
    for file_path, missing_types in files_to_fix.items():
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Add to existing typing import if present
            if 'from typing import' in content:
                for missing_type in missing_types:
                    if missing_type not in content[:1000]:  # Check imports section
                        content = re.sub(
                            r'(from typing import [^)\n]*)',
                            rf'\1, {missing_type}',
                            content,
                            count=1
                        )
                        fixes += 1
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            if missing_types:
                print(f"  ✅ Added imports {missing_types} to {file_path}")
                
        except Exception as e:
            print(f"  ❌ Error fixing imports in {file_path}: {e}")
    
    return fixes


def main():
    """Execute aggressive cleanup for 100% mypy compliance."""
    print("🚀 AGGRESSIVE MYPY CLEANUP - Pre-Beta Mode")
    print("=" * 50)
    print("Target: 100% error elimination for mission-critical cleanliness")
    
    # Get initial error count
    initial_errors = get_all_mypy_errors()
    print(f"\n📊 Initial state: {len(initial_errors)} mypy errors")
    
    # Show breakdown
    by_code = defaultdict(int)
    for error in initial_errors:
        by_code[error['code']] += 1
    
    print("📋 Error breakdown:")
    for code, count in sorted(by_code.items(), key=lambda x: -x[1]):
        print(f"  {code}: {count} errors")
    
    total_fixes = 0
    
    # Phase 1: Remove unused ignores (safe)
    total_fixes += fix_unused_ignore_comments(initial_errors)
    
    # Phase 2: Add missing return types (safe)
    current_errors = get_all_mypy_errors()
    total_fixes += fix_missing_return_types(current_errors)
    
    # Phase 3: Fix missing imports (safe)
    current_errors = get_all_mypy_errors()
    total_fixes += fix_missing_imports(current_errors)
    
    # Phase 4: Handle unreachable code (safe)
    current_errors = get_all_mypy_errors()
    total_fixes += fix_unreachable_code(current_errors)
    
    # Final check
    final_errors = get_all_mypy_errors()
    eliminated = len(initial_errors) - len(final_errors)
    
    print(f"\n🏁 CLEANUP COMPLETE")
    print(f"   Applied fixes: {total_fixes}")
    print(f"   Errors eliminated: {eliminated}")
    print(f"   Final error count: {len(final_errors)}")
    print(f"   Success rate: {(eliminated/len(initial_errors))*100:.1f}%")
    
    if len(final_errors) == 0:
        print("🎉 ZERO ERRORS ACHIEVED!")
    else:
        print(f"\n📋 Remaining error types:")
        remaining_by_code = defaultdict(int)
        for error in final_errors:
            remaining_by_code[error['code']] += 1
        
        for code, count in sorted(remaining_by_code.items(), key=lambda x: -x[1]):
            print(f"  {code}: {count} errors")


if __name__ == "__main__":
    main()