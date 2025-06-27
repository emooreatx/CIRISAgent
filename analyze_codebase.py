#!/usr/bin/env python3
"""
Analyze CIRIS codebase for duplicate classes, methods, and functions.
Output a structured JSON report for analysis.
"""

import ast
import json
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

class CodeAnalyzer(ast.NodeVisitor):
    """AST visitor to extract classes, methods, and functions."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.classes = []
        self.functions = []
        self.methods = []
        self.current_class = None
        
    def visit_ClassDef(self, node):
        """Visit class definitions."""
        class_info = {
            'name': node.name,
            'line': node.lineno,
            'decorators': [self.get_decorator_name(d) for d in node.decorator_list],
            'bases': [self.get_base_name(b) for b in node.bases],
            'methods': []
        }
        
        old_class = self.current_class
        self.current_class = class_info
        self.classes.append(class_info)
        
        # Visit methods
        self.generic_visit(node)
        
        self.current_class = old_class
        
    def visit_FunctionDef(self, node):
        """Visit function/method definitions."""
        func_info = {
            'name': node.name,
            'line': node.lineno,
            'decorators': [self.get_decorator_name(d) for d in node.decorator_list],
            'args': [arg.arg for arg in node.args.args],
            'is_async': isinstance(node, ast.AsyncFunctionDef)
        }
        
        if self.current_class:
            # It's a method
            func_info['class'] = self.current_class['name']
            self.current_class['methods'].append(func_info)
            self.methods.append(func_info)
        else:
            # It's a module-level function
            self.functions.append(func_info)
            
    def visit_AsyncFunctionDef(self, node):
        """Visit async function definitions."""
        self.visit_FunctionDef(node)
        
    def get_decorator_name(self, decorator):
        """Extract decorator name."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{decorator.attr}"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr
        return str(decorator)
        
    def get_base_name(self, base):
        """Extract base class name."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return f"{base.attr}"
        return str(base)

def analyze_file(filepath: Path) -> Dict:
    """Analyze a single Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = ast.parse(content)
        analyzer = CodeAnalyzer(str(filepath))
        analyzer.visit(tree)
        
        return {
            'file': str(filepath),
            'classes': analyzer.classes,
            'functions': analyzer.functions,
            'methods': analyzer.methods
        }
    except Exception as e:
        return {
            'file': str(filepath),
            'error': str(e),
            'classes': [],
            'functions': [],
            'methods': []
        }

def find_duplicates(all_data: List[Dict]) -> Dict:
    """Find duplicate classes, methods, and functions across files."""
    duplicates = {
        'classes': defaultdict(list),
        'methods': defaultdict(list),
        'functions': defaultdict(list),
        'method_signatures': defaultdict(list)
    }
    
    # Track classes
    for data in all_data:
        for cls in data['classes']:
            key = cls['name']
            duplicates['classes'][key].append({
                'file': data['file'],
                'line': cls['line'],
                'bases': cls['bases']
            })
            
    # Track methods (by class.method name)
    for data in all_data:
        for method in data['methods']:
            key = f"{method.get('class', 'Unknown')}.{method['name']}"
            duplicates['methods'][key].append({
                'file': data['file'],
                'line': method['line'],
                'class': method.get('class'),
                'args': method['args']
            })
            
    # Track functions
    for data in all_data:
        for func in data['functions']:
            key = func['name']
            duplicates['functions'][key].append({
                'file': data['file'],
                'line': func['line'],
                'args': func['args']
            })
            
    # Filter to only show actual duplicates
    duplicates['classes'] = {k: v for k, v in duplicates['classes'].items() if len(v) > 1}
    duplicates['methods'] = {k: v for k, v in duplicates['methods'].items() if len(v) > 1}
    duplicates['functions'] = {k: v for k, v in duplicates['functions'].items() if len(v) > 1}
    
    return duplicates

def analyze_codebase(root_dir: str) -> Dict:
    """Analyze entire codebase."""
    root_path = Path(root_dir)
    all_data = []
    
    # Analyze all Python files
    for py_file in root_path.rglob("*.py"):
        # Skip __pycache__ and other generated files
        if '__pycache__' in str(py_file) or '.pyc' in str(py_file):
            continue
            
        data = analyze_file(py_file)
        all_data.append(data)
    
    # Find duplicates
    duplicates = find_duplicates(all_data)
    
    # Create summary
    summary = {
        'total_files': len(all_data),
        'total_classes': sum(len(d['classes']) for d in all_data),
        'total_methods': sum(len(d['methods']) for d in all_data),
        'total_functions': sum(len(d['functions']) for d in all_data),
        'duplicate_classes': len(duplicates['classes']),
        'duplicate_methods': len(duplicates['methods']),
        'duplicate_functions': len(duplicates['functions'])
    }
    
    return {
        'summary': summary,
        'duplicates': duplicates,
        'all_files': all_data
    }

def main():
    """Main entry point."""
    # Analyze both ciris_engine and tests
    results = {
        'ciris_engine': analyze_codebase('ciris_engine'),
        'tests': analyze_codebase('tests')
    }
    
    # Save detailed results
    with open('codebase_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    print("=== CODEBASE ANALYSIS SUMMARY ===\n")
    
    for module in ['ciris_engine', 'tests']:
        summary = results[module]['summary']
        print(f"{module}:")
        print(f"  Files: {summary['total_files']}")
        print(f"  Classes: {summary['total_classes']} ({summary['duplicate_classes']} duplicates)")
        print(f"  Methods: {summary['total_methods']} ({summary['duplicate_methods']} duplicates)")
        print(f"  Functions: {summary['total_functions']} ({summary['duplicate_functions']} duplicates)")
        print()
    
    # Print notable duplicates
    print("=== NOTABLE DUPLICATES ===\n")
    
    for module in ['ciris_engine', 'tests']:
        duplicates = results[module]['duplicates']
        
        if duplicates['classes']:
            print(f"\nDuplicate classes in {module}:")
            for name, locations in list(duplicates['classes'].items())[:10]:
                print(f"  {name}:")
                for loc in locations:
                    print(f"    - {loc['file']}:{loc['line']}")
                    
        if duplicates['methods'] and module == 'ciris_engine':
            print(f"\nDuplicate methods in {module} (showing first 10):")
            for name, locations in list(duplicates['methods'].items())[:10]:
                if len(set(loc['file'] for loc in locations)) > 1:  # Only show cross-file duplicates
                    print(f"  {name}:")
                    for loc in locations:
                        print(f"    - {loc['file']}:{loc['line']}")
    
    print("\nFull analysis saved to: codebase_analysis.json")
    
    # Also create a CSV for easier analysis
    create_csv_report(results)

def create_csv_report(results):
    """Create CSV reports for easier analysis."""
    import csv
    
    # Create class inventory
    with open('class_inventory.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Module', 'File', 'Class', 'Line', 'Bases', 'Decorators'])
        
        for module in ['ciris_engine', 'tests']:
            for file_data in results[module]['all_files']:
                for cls in file_data['classes']:
                    writer.writerow([
                        module,
                        file_data['file'],
                        cls['name'],
                        cls['line'],
                        '|'.join(cls['bases']),
                        '|'.join(cls['decorators'])
                    ])
    
    # Create method inventory
    with open('method_inventory.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Module', 'File', 'Class', 'Method', 'Line', 'Args', 'Async', 'Decorators'])
        
        for module in ['ciris_engine', 'tests']:
            for file_data in results[module]['all_files']:
                for method in file_data['methods']:
                    writer.writerow([
                        module,
                        file_data['file'],
                        method.get('class', ''),
                        method['name'],
                        method['line'],
                        '|'.join(method['args']),
                        method.get('is_async', False),
                        '|'.join(method['decorators'])
                    ])
    
    print("\nCSV reports created:")
    print("  - class_inventory.csv")
    print("  - method_inventory.csv")

if __name__ == '__main__':
    main()