#!/usr/bin/env python3
"""Check alignment between protocols and implementations."""

import ast
import os
from typing import Dict, Set, List, Tuple
from pathlib import Path

def get_methods_from_class(node: ast.ClassDef) -> Set[str]:
    """Extract method names from a class definition."""
    methods = set()
    for item in node.body:
        if isinstance(item, ast.FunctionDef):
            if not item.name.startswith('_'):  # Skip private methods
                methods.add(item.name)
        elif isinstance(item, ast.AsyncFunctionDef):
            if not item.name.startswith('_'):
                methods.add(item.name)
    return methods

def find_protocols(directory: str) -> Dict[str, Set[str]]:
    """Find all protocols and their methods."""
    protocols = {}
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r') as f:
                    try:
                        tree = ast.parse(f.read())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                # Check if it's a Protocol
                                if any(base.id == 'Protocol' if isinstance(base, ast.Name) else 
                                      base.attr == 'Protocol' if isinstance(base, ast.Attribute) else False
                                      for base in node.bases):
                                    protocol_name = node.name
                                    methods = get_methods_from_class(node)
                                    if methods:
                                        protocols[protocol_name] = methods
                    except:
                        pass
    
    return protocols

def find_implementations(directory: str, protocol_name: str) -> List[Tuple[str, str, Set[str]]]:
    """Find classes that claim to implement a protocol."""
    implementations = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r') as f:
                    try:
                        content = f.read()
                        if protocol_name in content:
                            tree = ast.parse(content)
                            for node in ast.walk(tree):
                                if isinstance(node, ast.ClassDef):
                                    # Check if this class mentions the protocol
                                    for base in node.bases:
                                        base_name = ''
                                        if isinstance(base, ast.Name):
                                            base_name = base.id
                                        elif isinstance(base, ast.Attribute):
                                            base_name = base.attr
                                        
                                        if protocol_name in base_name:
                                            methods = get_methods_from_class(node)
                                            implementations.append((filepath, node.name, methods))
                    except:
                        pass
    
    return implementations

def main():
    # Find all protocols
    protocols = find_protocols('ciris_engine/protocols')
    print(f"Found {len(protocols)} protocols\n")
    
    # Check each protocol
    mismatches = []
    
    for protocol_name, protocol_methods in sorted(protocols.items()):
        if not protocol_methods:
            continue
            
        # Find implementations
        implementations = find_implementations('ciris_engine/logic', protocol_name)
        
        if implementations:
            print(f"\n{protocol_name} (methods: {', '.join(sorted(protocol_methods))})")
            print("-" * 80)
            
            for filepath, class_name, impl_methods in implementations:
                missing = protocol_methods - impl_methods
                extra = impl_methods - protocol_methods
                
                if missing or extra:
                    mismatches.append((protocol_name, class_name, missing, extra))
                    print(f"  {class_name} in {filepath}")
                    if missing:
                        print(f"    Missing: {', '.join(sorted(missing))}")
                    if extra:
                        print(f"    Extra: {', '.join(sorted(extra))}")
    
    print(f"\n\nSummary: Found {len(mismatches)} protocol/implementation mismatches")

if __name__ == "__main__":
    main()