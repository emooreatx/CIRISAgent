"""
Action schemas - shared across handlers, DMAs, and services.

These schemas define the parameters and results for all agent actions.
"""

# Import all action parameters
from .parameters import (
    # External actions
    ObserveParams,
    SpeakParams,
    ToolParams,

    # Control actions
    PonderParams,
    RejectParams,
    DeferParams,

    # Memory actions
    MemorizeParams,
    RecallParams,
    ForgetParams,

    # Terminal action
    TaskCompleteParams,
)

# Make them available at package level
__all__ = [
    # External
    "ObserveParams",
    "SpeakParams",
    "ToolParams",

    # Control
    "PonderParams",
    "RejectParams",
    "DeferParams",

    # Memory
    "MemorizeParams",
    "RecallParams",
    "ForgetParams",

    # Terminal
    "TaskCompleteParams",
]
