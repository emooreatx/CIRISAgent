#!/usr/bin/env python3
"""Script to find circular import dependencies in the CIRIS codebase."""

import ast
import os
import sys
from pathlib import Path
from collections import defaultdict, deque
from typing import Dict, Set, List, Tuple

def extract_imports(file_path: Path) -> List[str]:
    """Extract all import statements from a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        return imports
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []

def build_dependency_graph() -> Dict[str, Set[str]]:
    """Build a dependency graph of all Python modules."""
    ciris_root = Path("ciris_engine")
    graph = defaultdict(set)
    
    # Find all Python files
    for py_file in ciris_root.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
            
        # Convert file path to module name
        rel_path = py_file.relative_to(Path("."))
        module_name = str(rel_path).replace("/", ".").replace("\\", ".")[:-3]  # Remove .py
        
        # Extract imports
        imports = extract_imports(py_file)
        
        # Filter to only ciris_engine imports
        ciris_imports = []
        for imp in imports:
            if imp.startswith("ciris_engine"):
                ciris_imports.append(imp)
        
        graph[module_name] = set(ciris_imports)
    
    return graph

def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Find all cycles in the dependency graph using DFS."""
    visited = set()
    rec_stack = set()
    cycles = []
    
    def dfs(node: str, path: List[str]) -> None:
        if node in rec_stack:
            # Found a cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles.append(cycle)
            return
        
        if node in visited:
            return
            
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in graph.get(node, set()):
            dfs(neighbor, path.copy())
        
        rec_stack.remove(node)
    
    for node in graph:
        if node not in visited:
            dfs(node, [])
    
    return cycles

def main():
    print("🔍 Scanning for circular imports in ciris_engine...")
    
    # Build dependency graph
    graph = build_dependency_graph()
    
    print(f"📊 Found {len(graph)} modules")
    
    # Find cycles
    cycles = find_cycles(graph)
    
    if cycles:
        print(f"\n❌ Found {len(cycles)} circular import cycles:")
        for i, cycle in enumerate(cycles, 1):
            print(f"\n🔄 Cycle {i}:")
            for j, module in enumerate(cycle):
                arrow = " -> " if j < len(cycle) - 1 else ""
                print(f"   {module}{arrow}")
        
        # Show specific import relationships for cycles
        print(f"\n📋 Detailed import relationships:")
        for i, cycle in enumerate(cycles, 1):
            print(f"\n🔄 Cycle {i} details:")
            for j in range(len(cycle) - 1):
                module_a = cycle[j]
                module_b = cycle[j + 1]
                if module_b in graph.get(module_a, set()):
                    print(f"   {module_a} imports {module_b}")
    else:
        print("\n✅ No circular imports found!")
    
    # Show high-degree nodes (modules with many imports)
    print(f"\n📈 Modules with most dependencies:")
    sorted_modules = sorted(graph.items(), key=lambda x: len(x[1]), reverse=True)
    for module, deps in sorted_modules[:10]:
        if deps:
            print(f"   {module}: {len(deps)} imports")

if __name__ == "__main__":
    main()