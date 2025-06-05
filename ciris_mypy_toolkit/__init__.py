"""
CIRIS MyPy Toolkit - Ensuring Schema and Protocol Compliance

A comprehensive toolkit for maintaining type safety and protocol compliance
in the CIRIS Agent ecosystem. This toolkit helps developers and agents
building adapters/modules ensure they follow CIRIS schemas and protocols.

Key Features:
- Automated mypy error detection and fixing
- Schema compliance validation  
- Protocol interface verification
- Uncalled logic detection
- Internal method usage analysis
"""

from .core import CIRISMypyToolkit
from .analyzers import (
    SchemaValidator,
    ProtocolAnalyzer, 
    UnusedCodeDetector
)
from .error_fixers import (
    TypeAnnotationFixer,
    ProtocolComplianceFixer,
    SchemaAlignmentFixer
)

__version__ = "1.0.0"
__all__ = [
    "CIRISMypyToolkit",
    "SchemaValidator", 
    "ProtocolAnalyzer",
    "UnusedCodeDetector",
    "TypeAnnotationFixer",
    "ProtocolComplianceFixer", 
    "SchemaAlignmentFixer"
]