#!/usr/bin/env python3
"""
CIRIS MyPy Toolkit CLI - Command-line interface for the toolkit

Usage:
    python -m ciris_mypy_toolkit.cli analyze              # Analyze compliance
    python -m ciris_mypy_toolkit.cli fix --systematic     # Fix all issues systematically  
    python -m ciris_mypy_toolkit.cli validate adapter.py  # Validate specific adapter
    python -m ciris_mypy_toolkit.cli report               # Generate compliance report
"""

import argparse
import sys
import logging
from pathlib import Path

from .core import CIRISMypyToolkit

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="CIRIS MyPy Toolkit - Ensure schema and protocol compliance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s analyze                    # Full compliance analysis
    %(prog)s fix --systematic           # Systematic error fixing
    %(prog)s validate adapter.py        # Validate specific adapter
    %(prog)s report --output report.md  # Generate compliance report
    %(prog)s clean --unused-imports     # Clean unused imports
        """
    )
    
    parser.add_argument("command", 
                       choices=["analyze", "propose", "execute", "validate", "report", "clean"],
                       help="Command to execute")
    
    parser.add_argument("target", nargs="?", 
                       help="Target file/directory for validation")
    
    parser.add_argument("--systematic", action="store_true",
                       help="Use systematic error fixing approach")
    
    parser.add_argument("--categories", nargs="+",
                       choices=["type_annotations", "schema_alignment", 
                               "protocol_compliance", "unused_code_removal"],
                       help="Specific categories to fix")
    
    parser.add_argument("--output", "-o", 
                       help="Output file for reports")
    
    parser.add_argument("--unused-imports", action="store_true",
                       help="Clean unused imports")
    
    parser.add_argument("--target-dir", default="ciris_engine",
                       help="Target directory to analyze (default: ciris_engine)")
    
    parser.add_argument("--schemas-dir", default="ciris_engine/schemas", 
                       help="Schemas directory (default: ciris_engine/schemas)")
    
    args = parser.parse_args()
    
    # Initialize toolkit
    try:
        toolkit = CIRISMypyToolkit(args.target_dir, args.schemas_dir)
    except Exception as e:
        logger.error(f"Failed to initialize toolkit: {e}")
        sys.exit(1)
    
    # Execute command
    try:
        if args.command == "analyze":
            execute_analyze(toolkit)
            
        elif args.command == "propose":
            execute_propose(toolkit, args)
            
        elif args.command == "execute":
            execute_approved_fixes(toolkit, args)
            
        elif args.command == "validate":
            execute_validate(toolkit, args)
            
        elif args.command == "report":
            execute_report(toolkit, args)
            
        elif args.command == "clean":
            execute_clean(toolkit, args)
            
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


def execute_analyze(toolkit: CIRISMypyToolkit):
    """Execute compliance analysis."""
    print("🔍 CIRIS Compliance Analysis")
    print("=" * 50)
    
    analysis = toolkit.analyze_compliance()
    
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


def execute_propose(toolkit: CIRISMypyToolkit, args):
    """Execute proposal generation for agent review."""
    print("🔍 CIRIS Fix Proposal Generation")
    print("=" * 45)
    
    # Get initial error count
    initial_errors = len(toolkit.get_mypy_errors())
    print(f"Current mypy errors: {initial_errors}")
    
    # Generate proposal
    categories = args.categories or ["type_annotations"]
    output_file = args.output or "proposed_fixes.json"
    
    proposal_file = toolkit.propose_fixes(categories, output_file)
    
    print(f"\n📄 Proposal generated: {proposal_file}")
    print("🤖 AGENT: Please review the proposed changes in the file.")
    print(f"📋 To execute: python -m ciris_mypy_toolkit.cli execute {proposal_file}")


def execute_approved_fixes(toolkit: CIRISMypyToolkit, args):
    """Execute fixes from an approved proposal file."""
    if not args.target:
        logger.error("Proposal file required for execution")
        sys.exit(1)
    
    proposal_file = args.target
    
    print(f"🚀 Executing Approved Fixes")
    print("=" * 35)
    print(f"Proposal file: {proposal_file}")
    
    if not Path(proposal_file).exists():
        logger.error(f"Proposal file {proposal_file} not found")
        sys.exit(1)
    
    # Execute approved fixes
    results = toolkit.execute_approved_fixes(proposal_file)
    
    # Show results
    print(f"\n✅ Execution Results:")
    for category, count in results.items():
        if count > 0:
            print(f"   • {category}: {count} fixes applied")
    
    # Final verification
    final_errors = len(toolkit.get_mypy_errors())
    print(f"\n📈 Final Status:")
    print(f"   • Current mypy errors: {final_errors}")
    
    if final_errors == 0:
        print("🎉 ZERO ERRORS ACHIEVED!")


def execute_validate(toolkit: CIRISMypyToolkit, args):
    """Execute adapter validation."""
    if not args.target:
        logger.error("Target file required for validation")
        sys.exit(1)
    
    target_path = Path(args.target)
    
    print(f"🔍 Validating Adapter: {target_path}")
    print("=" * 50)
    
    results = toolkit.validate_adapter_compliance(str(target_path))
    
    if "error" in results:
        print(f"❌ Error: {results['error']}")
        return
    
    print(f"📊 Compliance Score: {results['compliance_score']:.1%}")
    print(f"🏗️ Schema Usage: {'✅' if results['schema_usage']['compliant'] else '❌'}")
    print(f"🔌 Protocol Implementation: {'✅' if results['protocol_implementation']['protocol_compliant'] else '❌'}")
    print(f"🎯 Type Safety: {'✅' if results['type_safety']['type_safe'] else '❌'}")
    
    # Show recommendations if any
    if results.get('recommendations'):
        print(f"\n💡 Recommendations:")
        for rec in results['recommendations']:
            print(f"   • {rec}")


def execute_report(toolkit: CIRISMypyToolkit, args):
    """Execute report generation."""
    print("📄 Generating Compliance Report...")
    
    report = toolkit.generate_compliance_report(args.output)
    
    if args.output:
        print(f"Report written to: {args.output}")
    else:
        print("\n" + report)


def execute_clean(toolkit: CIRISMypyToolkit, args):
    """Execute code cleaning."""
    print("🧹 Cleaning Unused Code")
    print("=" * 30)
    
    categories = []
    if args.unused_imports:
        categories.append("unused_imports")
    
    if not categories:
        categories = ["unused_imports"]  # Default safe cleaning
    
    removed = toolkit.unused_code_detector.remove_unused_code(categories)
    print(f"✅ Removed {removed} unused items")


if __name__ == "__main__":
    main()