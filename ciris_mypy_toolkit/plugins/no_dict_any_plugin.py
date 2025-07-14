"""
Mypy plugin to disallow Dict[str, Any] usage in CIRIS codebase.
This enforces the "No Dicts" philosophy by flagging any Dict[str, Any] usage.
"""

from typing import Callable, Optional, Type as TypingType
from mypy.plugin import Plugin, MethodContext
from mypy.nodes import (
    ARG_POS, ARG_STAR, ARG_STAR2, Argument, CallExpr, Decorator,
    FuncDef, MemberExpr, NameExpr, OpExpr, OverloadedFuncDef,
    TypeInfo, Var, TypeAlias
)
from mypy.types import (
    Type, AnyType, UnboundType, TypeList, UnionType,
    CallableType, TypedDictType, TypeType, Instance,
    get_proper_type
)


class NoDictAnyPlugin(Plugin):
    """Plugin that disallows Dict[str, Any] usage."""
    
    def get_type_analyze_hook(self, fullname: str) -> Optional[Callable[[Type], Type]]:
        """Hook into type analysis to check for Dict[str, Any]."""
        if fullname == "typing.Dict":
            return self._check_dict_type
        return None
    
    def _check_dict_type(self, typ: Type) -> Type:
        """Check if a Dict type has Any as value type."""
        proper_type = get_proper_type(typ)
        
        if isinstance(proper_type, Instance):
            # Check if this is Dict[str, Any]
            if (proper_type.type.fullname == "builtins.dict" and
                len(proper_type.args) == 2):
                key_type, value_type = proper_type.args
                
                # Check if key is str and value is Any
                key_proper = get_proper_type(key_type)
                value_proper = get_proper_type(value_type)
                
                if (isinstance(key_proper, Instance) and 
                    key_proper.type.fullname == "builtins.str" and
                    isinstance(value_proper, AnyType)):
                    
                    # Report error
                    self.fail(
                        "Dict[str, Any] is not allowed. "
                        "Use a specific Pydantic model instead.",
                        proper_type
                    )
        
        return typ
    
    def get_attribute_hook(self, fullname: str) -> Optional[Callable[[MethodContext], Type]]:
        """Hook for checking attributes and annotations."""
        # This allows us to check annotations in more contexts
        return None
    
    def get_decorator_hook(self, fullname: str) -> Optional[Callable[[Decorator], None]]:
        """Hook for checking decorators."""
        return None


def plugin(version: str) -> TypingType[Plugin]:
    """Entry point for mypy plugin."""
    return NoDictAnyPlugin