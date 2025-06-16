"""
Dynamic Action Instruction Generator for CIRIS Agent.

Generates action parameter schemas and instructions dynamically based on
registered action handlers and their parameter schemas.
"""

import logging
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel
import json

from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.action_params_v1 import (
    ObserveParams, SpeakParams, ToolParams, PonderParams, RejectParams,
    DeferParams, MemorizeParams, RecallParams, ForgetParams, TaskCompleteParams
)

logger = logging.getLogger(__name__)


class ActionInstructionGenerator:
    """Generates dynamic action instructions based on registered handlers and schemas."""
    
    # Map action types to their parameter schemas
    ACTION_PARAM_SCHEMAS: Dict[HandlerActionType, Type[BaseModel]] = {
        HandlerActionType.OBSERVE: ObserveParams,
        HandlerActionType.SPEAK: SpeakParams,
        HandlerActionType.TOOL: ToolParams,
        HandlerActionType.PONDER: PonderParams,
        HandlerActionType.REJECT: RejectParams,
        HandlerActionType.DEFER: DeferParams,
        HandlerActionType.MEMORIZE: MemorizeParams,
        HandlerActionType.RECALL: RecallParams,
        HandlerActionType.FORGET: ForgetParams,
        HandlerActionType.TASK_COMPLETE: TaskCompleteParams,
    }
    
    def __init__(self, service_registry: Optional[Any] = None, multi_service_sink: Optional[Any] = None):
        """Initialize with optional service registry and multi-service sink for tool discovery."""
        self.service_registry = service_registry
        self.multi_service_sink = multi_service_sink
        self._cached_instructions: Optional[str] = None
        
    def generate_action_instructions(self, available_actions: Optional[List[HandlerActionType]] = None) -> str:
        """Generate complete action parameter instructions dynamically."""
        
        if available_actions is None:
            available_actions = list(HandlerActionType)
        
        instructions = []
        instructions.append("Schemas for 'action_parameters' based on the selected_action:")
        
        for action_type in available_actions:
            if action_type in self.ACTION_PARAM_SCHEMAS:
                schema_text = self._generate_schema_for_action(action_type)
                if schema_text:
                    instructions.append(schema_text)
        
        return "\n".join(instructions)
    
    def _generate_schema_for_action(self, action_type: HandlerActionType) -> str:
        """Generate schema text for a specific action type."""
        
        param_class = self.ACTION_PARAM_SCHEMAS.get(action_type)
        if not param_class:
            return ""
        
        # Get the Pydantic schema
        schema = param_class.model_json_schema()
        
        # Custom formatting for each action type
        if action_type == HandlerActionType.SPEAK:
            return f"SPEAK: {{\"content\": string (required), \"channel_id\"?: string}}"
            
        elif action_type == HandlerActionType.PONDER:
            return f"PONDER: {{\"questions\": [string] (required list of 2-3 questions)}}"
            
        elif action_type == HandlerActionType.MEMORIZE:
            return self._format_memory_action_schema("MEMORIZE")
            
        elif action_type == HandlerActionType.RECALL:
            return self._format_memory_action_schema("RECALL")
            
        elif action_type == HandlerActionType.FORGET:
            return (f"FORGET: {{\"node\": {{id: string, type: \"agent\"|\"user\"|\"channel\"|\"concept\", "
                   f"scope: \"local\"|\"identity\"|\"environment\"}}, \"reason\": string (required)}}")
            
        elif action_type == HandlerActionType.DEFER:
            return (f"DEFER: {{\"reason\": string (required), \"context\"?: object, "
                   f"\"defer_until\"?: string (ISO timestamp like '2025-01-20T15:00:00Z')}}")
            return defer_schema + "\nUse defer_until for time-based deferrals that auto-reactivate."
            
        elif action_type == HandlerActionType.REJECT:
            reject_schema = (f"REJECT: {{\"reason\": string (required), "
                           f"\"create_filter\"?: boolean (default: false), "
                           f"\"filter_pattern\"?: string, "
                           f"\"filter_type\"?: \"regex\"|\"semantic\"|\"keyword\" (default: \"regex\"), "
                           f"\"filter_priority\"?: \"critical\"|\"high\"|\"medium\" (default: \"high\")}}")
            return reject_schema + "\nUse create_filter=true to prevent similar future requests."
            
        elif action_type == HandlerActionType.TOOL:
            return self._generate_tool_schema()
            
        elif action_type == HandlerActionType.OBSERVE:
            return (f"OBSERVE: {{\"channel_id\"?: string, \"active\"?: boolean (default: false), "
                   f"\"context\"?: object}}")
            
        elif action_type == HandlerActionType.TASK_COMPLETE:
            return (f"TASK_COMPLETE: {{\"completion_reason\"?: string (default: \"Task completed successfully\"), "
                   f"\"context\"?: object}}\n"
                   f"Use when task is done, impossible, unnecessary, or cannot be actioned. "
                   f"This is the preferred resolution for problematic tasks.")
        
        # Fallback to generic schema representation
        return f"{action_type.value.upper()}: {self._simplify_schema(schema)}"
    
    def _format_memory_action_schema(self, action_name: str) -> str:
        """Format schema for memory-related actions (MEMORIZE, RECALL)."""
        base_schema = (f"{action_name}: {{\"node\": {{id: string (unique identifier), "
                      f"type: \"agent\"|\"user\"|\"channel\"|\"concept\", "
                      f"scope: \"local\"|\"identity\"|\"environment\"")
        
        if action_name == "MEMORIZE":
            base_schema += ", attributes?: object (data to store)"
        
        base_schema += "}}"
        
        # Add guidance
        guidance = [
            f"\nFor type: use 'user' for user data, 'channel' for channel data, "
            f"'concept' for facts/beliefs/knowledge, 'agent' for agent data.",
            f"For scope: use 'local' for user/channel data, 'identity' for personal "
            f"facts/beliefs, 'environment' for external/internet data."
        ]
        
        return base_schema + "\n".join(guidance)
    
    def _generate_tool_schema(self) -> str:
        """Generate dynamic tool schema based on available tools."""
        base_schema = "TOOL: {\"name\": string (tool name), \"parameters\": object}"
        
        # If we have a service registry, try to get tools from all tool services
        if self.service_registry:
            try:
                # Get all tool services from the registry
                import asyncio
                loop = asyncio.get_event_loop()
                
                # Create a coroutine to get all tools
                async def get_all_tools():
                    tool_services = self.service_registry.get_services_by_type('tool')
                    all_tools = {}
                    
                    # Aggregate tools from all services
                    for tool_service in tool_services:
                        try:
                            service_tools = await tool_service.get_available_tools()
                            # Add service identifier to tool info
                            service_name = getattr(tool_service, 'adapter_name', type(tool_service).__name__)
                            
                            if isinstance(service_tools, list):
                                # If it returns a list of names, convert to dict
                                for tool_name in service_tools:
                                    all_tools[tool_name] = {
                                        'name': tool_name,
                                        'description': 'No description available',
                                        'service': service_name
                                    }
                            elif isinstance(service_tools, dict):
                                # If it returns a dict with details
                                for tool_name, tool_info in service_tools.items():
                                    # Create unique key if tool name exists in multiple services
                                    if tool_name in all_tools:
                                        tool_key = f"{tool_name}_{service_name}"
                                    else:
                                        tool_key = tool_name
                                    
                                    # Enhance tool info with service metadata
                                    enhanced_info = {
                                        'name': tool_name,
                                        'service': service_name,
                                        'description': tool_info.get('description', 'No description') if isinstance(tool_info, dict) else 'No description',
                                    }
                                    
                                    if isinstance(tool_info, dict):
                                        if 'parameters' in tool_info:
                                            enhanced_info['parameters'] = tool_info['parameters']
                                        if 'when_to_use' in tool_info:
                                            enhanced_info['when_to_use'] = tool_info['when_to_use']
                                    
                                    all_tools[tool_key] = enhanced_info
                                    
                        except Exception as e:
                            logger.warning(f"Failed to get tools from {type(tool_service).__name__}: {e}")
                    
                    return all_tools
                
                # Execute the coroutine
                all_tools = loop.run_until_complete(get_all_tools())
                    
                    if all_tools:
                        tools_info = []
                        tools_info.append("\nAvailable tools and their parameters:")
                        
                        for tool_key, tool_info in all_tools.items():
                            tool_desc = f"  - {tool_info['name']}: {tool_info['description']}"
                            if tool_info['service'] != tool_info['name']:
                                tool_desc += f" (from {tool_info['service']})"
                            tools_info.append(tool_desc)
                            
                            # Add parameter schema if available
                            if 'parameters' in tool_info:
                                param_text = f"    parameters: {json.dumps(tool_info['parameters'], indent=6)}"
                                tools_info.append(param_text)
                            
                            # Add usage guidance if available
                            if 'when_to_use' in tool_info:
                                tools_info.append(f"    Use when: {tool_info['when_to_use']}")
                        
                        return base_schema + "\n".join(tools_info)
                    
                except Exception as e:
                    logger.warning(f"Could not fetch tools via LIST_TOOLS: {e}")
        
        # Fallback: Include some known tools
        return base_schema + self._get_default_tool_instructions()
    
    def _get_default_tool_instructions(self) -> str:
        """Get default tool instructions when dynamic discovery isn't available."""
        return """
Available tools (check with tool service for current list):
  - discord_delete_message: Delete a message
    parameters: {"channel_id": integer, "message_id": integer}
  - discord_timeout_user: Temporarily mute a user
    parameters: {"guild_id": integer, "user_id": integer, "duration_seconds": integer, "reason"?: string}
  - discord_ban_user: Ban a user from the server
    parameters: {"guild_id": integer, "user_id": integer, "reason"?: string, "delete_message_days"?: integer}"""
    
    def _simplify_schema(self, schema: Dict[str, Any]) -> str:
        """Simplify a JSON schema to a readable format."""
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        params = []
        for prop_name, prop_schema in properties.items():
            prop_type = prop_schema.get("type", "any")
            if prop_name in required:
                params.append(f'"{prop_name}": {prop_type} (required)')
            else:
                default = prop_schema.get("default")
                if default is not None:
                    params.append(f'"{prop_name}"?: {prop_type} (default: {default})')
                else:
                    params.append(f'"{prop_name}"?: {prop_type}')
        
        return "{" + ", ".join(params) + "}"
    
    def get_action_guidance(self, action_type: HandlerActionType) -> str:
        """Get specific guidance for an action type."""
        
        guidance_map = {
            HandlerActionType.SPEAK: (
                "If 'Speak' is chosen, the 'action_parameters' MUST be a JSON object "
                "containing a 'content' key with the substantive response string."
            ),
            HandlerActionType.PONDER: (
                "If 'Ponder' is chosen, 'questions' MUST list 2-3 distinct, NEW questions "
                "to resolve ambiguity, building upon any previous ponder_notes."
            ),
            HandlerActionType.OBSERVE: (
                "If 'Observe' is chosen to gather more context, 'active' SHOULD generally "
                "be true to actively fetch recent information. Provide clear context."
            ),
            HandlerActionType.REJECT: (
                "Use 'Reject' only for requests that are fundamentally unserviceable, "
                "unethical, or malicious. Set create_filter=true to prevent similar requests."
            ),
            HandlerActionType.DEFER: (
                "Use 'Defer' ONLY when a task MUST be completed AND requires human approval. "
                "Most problematic tasks should be marked TASK_COMPLETE instead. "
                "Defer is for tasks that need doing but require human oversight."
            ),
            HandlerActionType.TASK_COMPLETE: (
                "Use 'TASK_COMPLETE' when: task is done, impossible, unnecessary, or unclear. "
                "This is preferred over DEFER for most situations where you cannot act."
            ),
        }
        
        return guidance_map.get(action_type, "")