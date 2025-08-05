#!/usr/bin/env python3
"""
Quality Analyzer CLI

Usage:
    python -m tools.quality_analyzer           # Run unified analysis
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Quality Analyzer - Unified analysis using ciris_mypy_toolkit and sonar_tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    args = parser.parse_args()
    
    from .analyzer import generate_unified_plan
    generate_unified_plan()


if __name__ == "__main__":
    main()