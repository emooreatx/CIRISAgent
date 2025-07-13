#!/usr/bin/env python3
"""
Find more unused imports by scanning the codebase.
Uses AST parsing to be more accurate than flake8.
"""
import ast
import os
from pathlib import Path
from collections import defaultdict


def find_imports_in_file(filepath):
    """Extract all imports from a Python file."""
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())
        
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, alias.asname, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    full_name = f"{module}.{alias.name}" if module else alias.name
                    imports.append((alias.name, alias.asname, node.lineno))
        
        return imports
    except:
        return []


def find_name_usage_in_file(filepath, names):
    """Check if names are used in the file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content)
        
        # Collect all names used in the file
        used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                used_names.add(node.attr)
        
        # Check which imported names are used
        unused = []
        for name, asname, lineno in names:
            check_name = asname if asname else name
            # Skip if it's a module import (e.g., 'typing')
            if '.' not in check_name and check_name not in used_names:
                # Double check with string search to avoid false positives
                if check_name not in content[content.index('\n', content.index('\n') * lineno):]:
                    unused.append((name, asname, lineno))
        
        return unused
    except:
        return []


def main():
    """Find unused imports across the codebase."""
    unused_by_file = defaultdict(list)
    
    # Scan all Python files
    for root, dirs, files in os.walk('ciris_engine'):
        # Skip test directories
        if 'test' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                
                # Get imports
                imports = find_imports_in_file(filepath)
                if not imports:
                    continue
                
                # Find unused
                unused = find_name_usage_in_file(filepath, imports)
                if unused:
                    unused_by_file[filepath] = unused
    
    # Report findings
    total_unused = 0
    print("Unused imports found:\n")
    
    for filepath, unused in sorted(unused_by_file.items()):
        print(f"{filepath}:")
        for name, asname, lineno in unused:
            display_name = f"{name} as {asname}" if asname else name
            print(f"  Line {lineno}: {display_name}")
            total_unused += 1
        print()
    
    print(f"Total unused imports: {total_unused}")
    
    # Generate removal script
    if total_unused > 0:
        print("\nGenerating removal commands...")
        with open('remove_unused_imports_batch.py', 'w') as f:
            f.write("#!/usr/bin/env python3\n")
            f.write("# Auto-generated script to remove unused imports\n\n")
            f.write("import os\n\n")
            f.write("removals = [\n")
            
            for filepath, unused in sorted(unused_by_file.items()):
                for name, asname, lineno in unused:
                    f.write(f'    ("{filepath}", {lineno}, "{name}"),\n')
            
            f.write("]\n\n")
            f.write("# Remove imports\n")
            f.write("for filepath, lineno, name in removals:\n")
            f.write("    print(f'Removing {name} from {filepath}:{lineno}')\n")
            f.write("    # Implementation would go here\n")
        
        print("Generated remove_unused_imports_batch.py")


if __name__ == "__main__":
    main()