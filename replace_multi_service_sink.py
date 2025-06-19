#!/usr/bin/env python3
"""
Replace all occurrences of multi_service_sink with bus_manager
"""

import os
import re

def replace_in_file(filepath):
    """Replace multi_service_sink with bus_manager in a file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Replace multi_service_sink with bus_manager
    content = content.replace('multi_service_sink', 'bus_manager')
    
    # Fix any double references like bus_manager returns bus_manager
    content = content.replace('bus_manager returns bus_manager', 'multi_service_sink returns bus_manager')
    
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Updated {filepath}")
        return True
    return False

def main():
    """Replace multi_service_sink with bus_manager in all Python files."""
    count = 0
    
    # Process ciris_engine directory
    for root, dirs, files in os.walk('ciris_engine'):
        # Skip __pycache__ directories
        if '__pycache__' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if replace_in_file(filepath):
                    count += 1
    
    # Process tests directory
    for root, dirs, files in os.walk('tests'):
        # Skip __pycache__ directories
        if '__pycache__' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if replace_in_file(filepath):
                    count += 1
    
    print(f"\nTotal files updated: {count}")

if __name__ == "__main__":
    main()