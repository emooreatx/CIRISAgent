from typing import Callable, Dict, Any, Optional, List
from ciris_engine.schemas.tool_schemas_v1 import ToolDescription, ToolParameter

class ToolRegistry:
    """Central registry for available tools and their schemas."""
    def __init__(self) -> None:
        self._tools: Dict[str, ToolDescription] = {}
        self._handlers: Dict[str, Callable] = {}

    def register_tool(self, name: str, schema: Dict[str, Any], handler: Callable) -> None:
        """Register a tool with its argument schema and handler.
        
        Args:
            name: Tool name
            schema: Dict with parameter descriptions (legacy format)
            handler: Callable that executes the tool
        """
        # Convert legacy schema format to ToolDescription
        tool_desc = self._convert_legacy_schema(name, schema)
        self._tools[name] = tool_desc
        self._handlers[name] = handler

    def register_tool_v2(self, tool_description: ToolDescription, handler: Callable) -> None:
        """Register a tool with its full description and handler (new format)."""
        self._tools[tool_description.name] = tool_description
        self._handlers[tool_description.name] = handler

    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get the argument schema for a tool (legacy format for compatibility)."""
        tool_desc = self._tools.get(name)
        if not tool_desc:
            return None
        # Convert back to legacy format
        return {param.name: param.type.value for param in tool_desc.parameters}

    def get_tool_description(self, name: str) -> Optional[ToolDescription]:
        """Get the full tool description."""
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDescription]:
        """List all registered tools."""
        return list(self._tools.values())

    def validate_arguments(self, name: str, arguments: Dict[str, Any]) -> bool:
        """Validate tool arguments against schema."""
        tool_desc = self._tools.get(name)
        if not tool_desc:
            return False
            
        # Check required parameters
        for param in tool_desc.parameters:
            if param.required and param.name not in arguments:
                return False
                
        # Check parameter types (basic validation)
        for param_name, param_value in arguments.items():
            param_def = next((p for p in tool_desc.parameters if p.name == param_name), None)
            if not param_def:
                # Unknown parameter
                continue
                
            # Basic type validation
            if param_def.type.value == "string" and not isinstance(param_value, str):
                return False
            elif param_def.type.value == "integer" and not isinstance(param_value, int):
                return False
            elif param_def.type.value == "float" and not isinstance(param_value, (int, float)):
                return False
            elif param_def.type.value == "boolean" and not isinstance(param_value, bool):
                return False
                
        return True

    def get_handler(self, name: str) -> Optional[Callable]:
        return self._handlers.get(name)
    
    def _convert_legacy_schema(self, name: str, schema: Dict[str, Any]) -> ToolDescription:
        """Convert legacy schema format to ToolDescription."""
        parameters = []
        for param_name, param_type in schema.items():
            # Handle tuple format like (str, type(None))
            if isinstance(param_type, tuple):
                # Legacy format for optional parameters
                required = False
                param_type_str = "string"  # Default to string
            else:
                required = True
                param_type_str = "string"  # Default to string
                
            parameters.append(ToolParameter(
                name=param_name,
                type=param_type_str,  # type: ignore
                description=f"Parameter {param_name}",
                required=required
            ))
            
        return ToolDescription(
            name=name,
            description=f"Tool {name}",
            parameters=parameters
        )
