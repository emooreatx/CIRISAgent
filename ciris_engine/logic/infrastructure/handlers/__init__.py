"""Infrastructure handlers module - exports base handler only."""

from .base_handler import BaseActionHandler, ActionHandlerDependencies

__all__ = [
    "BaseActionHandler",
    "ActionHandlerDependencies",
]
