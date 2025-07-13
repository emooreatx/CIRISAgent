#!/usr/bin/env python3
"""
Safe removal of unused imports identified by flake8.
Processes one file at a time and validates each change.
"""
import ast
import sys
import subprocess
from pathlib import Path


def get_unused_imports():
    """Get list of unused imports from flake8."""
    result = subprocess.run(
        ["flake8", "ciris_engine/", "--select=F401", "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s"],
        capture_output=True,
        text=True
    )
    
    unused = []
    for line in result.stdout.splitlines():
        if "F401" in line:
            parts = line.split(":", 4)
            if len(parts) >= 5:
                filepath = parts[0]
                line_num = int(parts[1])
                # Extract the imported name from the message
                msg = parts[4]
                if "imported but unused" in msg:
                    # Extract the module/name between quotes
                    import_name = msg.split("'")[1]
                    unused.append((filepath, line_num, import_name))
    
    return unused


def remove_unused_import(filepath, line_num, import_name):
    """Remove a specific unused import from a file."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Adjust for 0-based indexing
    line_idx = line_num - 1
    
    if line_idx >= len(lines):
        return False
    
    line = lines[line_idx]
    
    # Handle different import styles
    if f"import {import_name}" in line:
        # Simple case: import module
        if line.strip() == f"import {import_name}":
            # Remove the entire line
            lines.pop(line_idx)
        else:
            # Part of a multi-import line, need to be careful
            return False
    elif f"from " in line and import_name in line:
        # from module import name case
        if ", " in line:
            # Multiple imports on one line
            # This is complex to handle safely, skip for now
            return False
        else:
            # Single import, safe to remove
            lines.pop(line_idx)
    else:
        return False
    
    # Write back
    with open(filepath, 'w') as f:
        f.writelines(lines)
    
    return True


def validate_file(filepath):
    """Validate a Python file still compiles after changes."""
    try:
        with open(filepath, 'r') as f:
            ast.parse(f.read())
        return True
    except SyntaxError:
        return False


def main():
    """Main execution."""
    print("Collecting unused imports...")
    unused_imports = get_unused_imports()
    print(f"Found {len(unused_imports)} unused imports")
    
    # Group by file
    by_file = {}
    for filepath, line_num, import_name in unused_imports:
        if filepath not in by_file:
            by_file[filepath] = []
        by_file[filepath].append((line_num, import_name))
    
    removed_count = 0
    failed_files = []
    
    for filepath, imports in by_file.items():
        print(f"\nProcessing {filepath} ({len(imports)} unused imports)")
        
        # Sort by line number in reverse to avoid line number shifts
        imports.sort(reverse=True)
        
        file_removed = 0
        for line_num, import_name in imports:
            if remove_unused_import(filepath, line_num, import_name):
                file_removed += 1
            else:
                print(f"  Skipped complex import: {import_name} at line {line_num}")
        
        # Validate the file
        if not validate_file(filepath):
            print(f"  ERROR: File has syntax errors after changes!")
            failed_files.append(filepath)
        else:
            removed_count += file_removed
            if file_removed > 0:
                print(f"  Removed {file_removed} imports")
    
    print(f"\nSummary:")
    print(f"  Total removed: {removed_count}")
    print(f"  Failed files: {len(failed_files)}")
    
    if failed_files:
        print("\nFailed files:")
        for f in failed_files:
            print(f"  {f}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())