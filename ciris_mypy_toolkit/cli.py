#!/usr/bin/env python3
"""
CIRIS MyPy Toolkit CLI - Command-line interface for the toolkit

Usage:
    python -m ciris_mypy_toolkit.cli analyze              # Analyze compliance
    python -m ciris_mypy_toolkit.cli fix --systematic     # Fix all issues systematically  
    python -m ciris_mypy_toolkit.cli validate adapter.py  # Validate specific adapter
    python -m ciris_mypy_toolkit.cli report               # Generate compliance report
    python -m ciris_mypy_toolkit.cli simplify_engine      # Generate engine simplification proposals
"""

import sys
import os
import logging
import click
from ciris_mypy_toolkit.core import CIRISMypyToolkit
from ciris_mypy_toolkit.analyzers.engine_simplifier import generate_engine_simplification_proposals

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Initialize toolkit globally for all commands
TOOLKIT = CIRISMypyToolkit("ciris_engine", "ciris_engine/schemas")

@click.group()
def main():
    """CIRIS MyPy Toolkit - Ensure schema and protocol compliance"""
    pass

@main.command()
def analyze():
    """Execute compliance analysis."""
    print("🔍 CIRIS Compliance Analysis")
    print("=" * 50)
    analysis = TOOLKIT.analyze_compliance()
    print(f"\n📊 MyPy Type Safety:")
    print(f"   Total Errors: {analysis['total_mypy_errors']}")
    if analysis['error_categories']:
        print("   Error Categories:")
        for category, errors in analysis['error_categories'].items():
            print(f"     • {category}: {len(errors)} errors")
    print(f"\n🏗️ Schema Compliance:")
    print(f"   Issues Found: {analysis['schema_compliance']['total_issues']}")
    print(f"\n🔌 Protocol Compliance:")
    print(f"   Issues Found: {analysis['protocol_compliance']['total_issues']}")
    print(f"\n🧹 Code Quality:")
    print(f"   Unused Code Items: {analysis['unused_code']['total_items']}")
    if analysis['recommendations']:
        print(f"\n💡 Recommendations:")
        for rec in analysis['recommendations']:
            print(f"   • {rec}")

@main.command()
@click.option('--categories', multiple=True, default=["type_annotations"], help="Categories to propose fixes for.")
@click.option('--output', default="proposed_fixes.json", help="Output file for proposals.")
def propose(categories, output):
    """Execute proposal generation for agent review."""
    print("🔍 CIRIS Fix Proposal Generation")
    print("=" * 45)
    initial_errors = len(TOOLKIT.get_mypy_errors())
    print(f"Current mypy errors: {initial_errors}")
    proposal_file = TOOLKIT.propose_fixes(list(categories), output)
    print(f"\n📄 Proposal generated: {proposal_file}")
    print("🤖 AGENT: Please review the proposed changes in the file.")
    print(f"📋 To execute: python -m ciris_mypy_toolkit execute --target {proposal_file}")

@main.command()
@click.option('--target', required=True, help="Proposal file to execute.")
def execute(target):
    """Execute fixes from an approved proposal file."""
    print(f"🚀 Executing Approved Fixes")
    print("=" * 35)
    print(f"Proposal file: {target}")
    import pathlib
    if not pathlib.Path(target).exists():
        logger.error(f"Proposal file {target} not found")
        sys.exit(1)
    results = TOOLKIT.execute_approved_fixes(target)
    print(f"\n✅ Execution Results:")
    for category, count in results.items():
        if count > 0:
            print(f"   • {category}: {count} fixes applied")
    final_errors = len(TOOLKIT.get_mypy_errors())
    print(f"\n📈 Final Status:")
    print(f"   • Current mypy errors: {final_errors}")
    if final_errors == 0:
        print("🎉 ZERO ERRORS ACHIEVED!")

@main.command()
@click.argument('target')
def validate(target):
    """Execute adapter validation."""
    import pathlib
    print(f"🔍 Validating Adapter: {target}")
    print("=" * 50)
    results = TOOLKIT.validate_adapter_compliance(str(pathlib.Path(target)))
    if "error" in results:
        print(f"❌ Error: {results['error']}")
        return
    print(f"📊 Compliance Score: {results['compliance_score']:.1%}")
    print(f"🏗️ Schema Usage: {'✅' if results['schema_usage']['compliant'] else '❌'}")
    print(f"🔌 Protocol Implementation: {'✅' if results['protocol_implementation']['protocol_compliant'] else '❌'}")
    print(f"🎯 Type Safety: {'✅' if results['type_safety']['type_safe'] else '❌'}")
    if results.get('recommendations'):
        print(f"\n💡 Recommendations:")
        for rec in results['recommendations']:
            print(f"   • {rec}")

@main.command()
@click.option('--output', default=None, help="Output file for the report.")
def report(output):
    """Generate compliance report."""
    report = TOOLKIT.generate_compliance_report(output)
    if output:
        print(f"Report written to: {output}")
    else:
        print(report)

@main.command()
@click.option('--output', default="ciris_mypy_toolkit/reports/engine_simplification_proposals.json", help="Output file for the simplification proposals.")
def simplify_engine(output):
    """Generate engine simplification proposals using the hot/cold path map."""
    engine_root = "ciris_engine"
    hot_cold_map_path = "ciris_mypy_toolkit/reports/hot_cold_path_map.json"
    generate_engine_simplification_proposals(engine_root, hot_cold_map_path, output)
    print(f"Engine simplification proposals written to {output}")

if __name__ == "__main__":
    main()