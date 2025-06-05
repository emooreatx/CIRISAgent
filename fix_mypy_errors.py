#!/usr/bin/env python3
"""
Smart mypy error fixer - works WITH AI to fix type errors safely
"""
import re
import subprocess
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional

class SmartMypyFixer:
    def __init__(self, target_dir: str = "ciris_engine"):
        self.target_dir = target_dir
        self.fixes_applied = 0
        
    def get_mypy_errors(self) -> List[Dict[str, str]]:
        """Run mypy and parse errors."""
        cmd = f"python -m mypy {self.target_dir} --ignore-missing-imports --show-error-codes --no-error-summary"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        errors = []
        # Mypy outputs to stderr
        output = result.stderr
        
        # Parse multiline mypy errors
        current_error = None
        for line in output.splitlines():
            # Match error line with file:line:col format
            match = re.search(r'^([^:]+):(\d+):(\d+):\s*error:\s*(.+)', line)
            if match:
                current_error = {
                    'file': match.group(1),
                    'line': int(match.group(2)),
                    'col': int(match.group(3)),
                    'message': match.group(4).strip(),
                    'code': ''
                }
            elif current_error and '[' in line and ']' in line:
                # Extract error code from continuation line
                code_match = re.search(r'\[([^\]]+)\]', line)
                if code_match:
                    current_error['code'] = code_match.group(1)
                    errors.append(current_error)
                    current_error = None
                    
        return errors

    def fix_missing_return_type(self, file_path: str, line_num: int) -> bool:
        """Add -> None to functions missing return type."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            if line_num > len(lines):
                return False
                
            line = lines[line_num - 1]
            
            # Check if it's a function definition without return type
            if re.match(r'^\s*def\s+\w+\(.*\)\s*:\s*$', line):
                # Add -> None before the colon
                lines[line_num - 1] = re.sub(r'\)\s*:', ') -> None:', line)
                
                with open(file_path, 'w') as f:
                    f.writelines(lines)
                
                self.fixes_applied += 1
                return True
        except Exception as e:
            print(f"Error fixing {file_path}:{line_num}: {e}")
        return False

    def fix_optional_access(self, file_path: str, line_num: int) -> bool:
        """Fix union-attr errors by adding None checks."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            if line_num > len(lines):
                return False
            
            line = lines[line_num - 1]
            
            # Look for attribute access that might be None
            match = re.search(r'(\w+)\.(\w+)', line)
            if match:
                var_name = match.group(1)
                indent = re.match(r'^(\s*)', line).group(1)
                
                # Add a None check before this line
                check_line = f"{indent}if {var_name} is not None:\n"
                new_indent = indent + "    "
                lines[line_num - 1] = new_indent + line.lstrip()
                lines.insert(line_num - 1, check_line)
                
                with open(file_path, 'w') as f:
                    f.writelines(lines)
                
                self.fixes_applied += 1
                return True
        except Exception as e:
            print(f"Error fixing {file_path}:{line_num}: {e}")
        return False

    def batch_fix_errors(self):
        """Fix all errors in batches by type for maximum efficiency."""
        print("🔍 Analyzing mypy errors...")
        errors = self.get_mypy_errors()
        
        # Group errors by type
        error_groups = defaultdict(list)
        for error in errors:
            error_groups[error['code']].append(error)
        
        print(f"\n📊 Found {len(errors)} errors in {len(error_groups)} categories:")
        for code, group in sorted(error_groups.items(), key=lambda x: -len(x[1])):
            print(f"  {code}: {len(group)} errors")
        
        # Fix errors by type for efficiency
        print("\n🔧 Applying fixes...")
        
        # 1. Fix all missing return types first (most common)
        if 'no-untyped-def' in error_groups:
            print(f"\n✨ Fixing {len(error_groups['no-untyped-def'])} missing return types...")
            for error in error_groups['no-untyped-def']:
                if 'missing a return type annotation' in error['message']:
                    self.fix_missing_return_type(error['file'], error['line'])
        
        # 2. Fix union-attr errors
        if 'union-attr' in error_groups:
            print(f"\n✨ Fixing {len(error_groups['union-attr'])} union-attr errors...")
            for error in error_groups['union-attr']:
                self.fix_optional_access(error['file'], error['line'])
        
        print(f"\n✅ Applied {self.fixes_applied} fixes!")
        
        # Show remaining errors
        print("\n📈 Re-running mypy to check progress...")
        new_errors = self.get_mypy_errors()
        print(f"Errors reduced from {len(errors)} to {len(new_errors)} ({len(errors) - len(new_errors)} fixed)")
        
        return len(errors) - len(new_errors)

    def auto_fix_common_patterns(self):
        """Apply common pattern fixes across all files."""
        print("\n🎯 Applying pattern-based fixes...")
        
        files_modified = 0
        for file_path in Path(self.target_dir).rglob('*.py'):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                original = content
                
                # Fix db_path parameters without type hints
                content = re.sub(r'(\w+\(.*?)(\w+)=None(\))', r'\1\2: Optional[str] = None\3', content)
                
                # Fix common Optional imports missing
                if 'Optional[' in content and 'from typing import' in content and 'Optional' not in content[:500]:
                    content = re.sub(r'(from typing import [^)\n]*)', r'\1, Optional', content)
                
                if content != original:
                    with open(file_path, 'w') as f:
                        f.write(content)
                    files_modified += 1
                    self.fixes_applied += 1
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
        
        print(f"Modified {files_modified} files with pattern fixes")

    def analyze_specific_errors(self, error_type: str, file_pattern: Optional[str] = None, limit: int = 10):
        """Analyze specific error types and propose fixes."""
        print(f"🔍 Analyzing {error_type} errors...")
        errors = self.get_mypy_errors()
        
        # Filter by error type and file pattern
        filtered_errors = [e for e in errors if e['code'] == error_type]
        if file_pattern:
            filtered_errors = [e for e in filtered_errors if file_pattern in e['file']]
        
        if not filtered_errors:
            print(f"No {error_type} errors found!")
            return
        
        print(f"Found {len(filtered_errors)} {error_type} errors")
        
        # Show first few errors with context
        for i, error in enumerate(filtered_errors[:limit]):
            print(f"\n📍 Error {i+1}: {error['file']}:{error['line']}")
            print(f"   Message: {error['message']}")
            
            # Show file context
            try:
                with open(error['file'], 'r') as f:
                    lines = f.readlines()
                
                line_num = error['line']
                start = max(0, line_num - 3)
                end = min(len(lines), line_num + 2)
                
                print("   Context:")
                for j in range(start, end):
                    marker = " ➤ " if j == line_num - 1 else "   "
                    print(f"{marker}{j+1:3}: {lines[j].rstrip()}")
                    
            except Exception as e:
                print(f"   Could not read file: {e}")
    
    def propose_fix(self, file_path: str, line_num: int, error_code: str, error_msg: str) -> Optional[str]:
        """Propose a specific fix for an error."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            if line_num > len(lines):
                return None
            
            line = lines[line_num - 1]
            
            if error_code == "no-untyped-def":
                if "missing a return type annotation" in error_msg:
                    if re.search(r'def\s+\w+\([^)]*\)\s*:\s*$', line):
                        return line.replace('):', ') -> None:')
            
            elif error_code == "assignment":
                if "default has type \"None\"" in error_msg:
                    match = re.search(r'(\w+): (\w+) = None', line)
                    if match:
                        param_name, param_type = match.groups()
                        return line.replace(f'{param_name}: {param_type} = None', 
                                          f'{param_name}: Optional[{param_type}] = None')
            
            elif error_code == "attr-defined":
                if "append" in error_msg and '"object"' in error_msg:
                    if ' = {' in line and ':' not in line.split('=')[0]:
                        var_part = line.split('=')[0].strip()
                        return line.replace(var_part, f'{var_part}: Dict[str, Any]')
            
            return None
        except Exception:
            return None
    
    def apply_fix(self, file_path: str, line_num: int, old_line: str, new_line: str) -> bool:
        """Apply a specific fix with verification."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            if lines[line_num - 1].strip() != old_line.strip():
                print(f"❌ Line changed since analysis: {file_path}:{line_num}")
                return False
            
            lines[line_num - 1] = new_line
            
            with open(file_path, 'w') as f:
                f.writelines(lines)
            
            print(f"✅ Applied fix to {file_path}:{line_num}")
            self.fixes_applied += 1
            return True
            
        except Exception as e:
            print(f"❌ Error applying fix: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Smart mypy error fixer")
    parser.add_argument("command", choices=["analyze", "count", "fix"], help="Command to run")
    parser.add_argument("--type", help="Error type to focus on (e.g., no-untyped-def, assignment)")
    parser.add_argument("--file", help="File pattern to filter")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of errors to show")
    parser.add_argument("--apply", action="store_true", help="Apply proposed fixes")
    
    args = parser.parse_args()
    
    fixer = SmartMypyFixer()
    
    print("🤖 Smart Mypy Fixer - AI Collaborative Edition")
    print("=" * 50)
    
    if args.command == "count":
        errors = fixer.get_mypy_errors()
        error_groups = defaultdict(list)
        for error in errors:
            error_groups[error['code']].append(error)
        
        print(f"📊 Found {len(errors)} total errors:")
        for code, group in sorted(error_groups.items(), key=lambda x: -len(x[1])):
            print(f"  {code}: {len(group)} errors")
    
    elif args.command == "analyze":
        if not args.type:
            print("❌ --type required for analyze command")
            sys.exit(1)
        
        fixer.analyze_specific_errors(args.type, args.file, args.limit)
        
        if args.apply:
            print(f"\n🔧 Proposing fixes for {args.type} errors...")
            errors = fixer.get_mypy_errors()
            filtered_errors = [e for e in errors if e['code'] == args.type]
            if args.file:
                filtered_errors = [e for e in filtered_errors if args.file in e['file']]
            
            for error in filtered_errors[:args.limit]:
                proposed = fixer.propose_fix(error['file'], error['line'], error['code'], error['message'])
                if proposed:
                    try:
                        with open(error['file'], 'r') as f:
                            lines = f.readlines()
                        original = lines[error['line'] - 1]
                        
                        print(f"\n📝 {error['file']}:{error['line']}")
                        print(f"   Original: {original.strip()}")
                        print(f"   Proposed: {proposed.strip()}")
                        
                        response = input("   Apply this fix? (y/n/q): ").lower()
                        if response == 'y':
                            fixer.apply_fix(error['file'], error['line'], original, proposed)
                        elif response == 'q':
                            break
                    except Exception as e:
                        print(f"   Error: {e}")
    
    elif args.command == "fix":
        print("🔧 Running batch fixes...")
        fixer.batch_fix_errors()

if __name__ == "__main__":
    main()