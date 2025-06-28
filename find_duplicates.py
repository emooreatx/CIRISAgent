#!/usr/bin/env python3
"""Find duplicate class definitions in the codebase."""

import os
import re
from collections import defaultdict
from pathlib import Path

def find_class_definitions(root_dir="ciris_engine"):
    """Find all class definitions and their locations."""
    class_locations = defaultdict(list)
    
    for root, dirs, files in os.walk(root_dir):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            # Match class definitions
                            match = re.match(r'^class\s+(\w+)', line)
                            if match:
                                class_name = match.group(1)
                                # Get the next few lines for context
                                context_lines = lines[i:min(i+5, len(lines))]
                                context = ''.join(context_lines).strip()
                                
                                class_locations[class_name].append({
                                    'file': filepath,
                                    'line': i + 1,
                                    'context': context[:200]  # First 200 chars
                                })
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return class_locations

def analyze_duplicates(class_locations):
    """Analyze and report duplicate classes."""
    duplicates = {name: locs for name, locs in class_locations.items() if len(locs) > 1}
    
    if not duplicates:
        print("No duplicate class names found!")
        return
    
    # Sort by number of occurrences
    sorted_dups = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)
    
    print(f"Found {len(duplicates)} duplicate class names:\n")
    
    for class_name, locations in sorted_dups:
        print(f"{'='*60}")
        print(f"Class: {class_name} ({len(locations)} occurrences)")
        print(f"{'='*60}")
        
        for loc in locations:
            print(f"\nFile: {loc['file']}:{loc['line']}")
            print("Context:")
            print(loc['context'])
        
        print()

if __name__ == "__main__":
    print("Scanning for duplicate class definitions...\n")
    class_locations = find_class_definitions()
    analyze_duplicates(class_locations)