from typing import Optional, Any, List, Union
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.actions import (
    SpeakParams, MemorizeParams, RecallParams, PonderParams,
    ObserveParams, ToolParams, RejectParams, DeferParams,
    ForgetParams, TaskCompleteParams
)

# Union type for all action parameters - 100% schema compliant
ActionParams = Union[
    SpeakParams, MemorizeParams, RecallParams, PonderParams,
    ObserveParams, ToolParams, RejectParams, DeferParams,
    ForgetParams, TaskCompleteParams
]
from ciris_engine.schemas.runtime.enums import HandlerActionType
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope, GraphNodeAttributes
from ciris_engine.logic.utils.channel_utils import create_channel_context
from typing import Any
from typing import List
from typing import Set
from typing import Union

def action_selection(context: Optional[List[Any]] = None, messages: Optional[List[dict]] = None) -> ActionSelectionDMAResult:
    """Mock ActionSelectionDMAResult with passing values and protocol-compliant types."""
    context = context or []
    messages = messages or []
    
    # Debug context parsing
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"[MOCK_LLM] Context items: {len(context)}")
    logger.debug(f"[MOCK_LLM] Messages count: {len(messages)}")
    if messages:
        for i, msg in enumerate(messages[:3]):  # First 3 messages
            role = msg.get('role', 'unknown') if isinstance(msg, dict) else 'not-dict'
            content_preview = str(msg.get('content', ''))[:100] if isinstance(msg, dict) else str(msg)[:100]
            logger.debug(f"[MOCK_LLM] Message {i}: role={role}, content={content_preview}...")
    
    # If messages not provided, try to extract from context for backwards compatibility
    if not messages:
        for item in context:
            if item.startswith("__messages__:"):
                import json
                try:
                    messages = json.loads(item.split(":", 1)[1])
                except:
                    pass
                break
    
    # Extract channel from context - check multiple patterns
    channel_id = "cli"  # Default to cli instead of test
    for item in context:
        # Check for echo_channel pattern from responses.py
        if item.startswith("echo_channel:"):
            channel_id = item.split(":", 1)[1].strip()
            break
        # Check for channel_id pattern
        elif item.startswith("channel_id:"):
            channel_id = item.split(":", 1)[1].strip()
            break
        # Check for channel context patterns
        elif "channel" in str(item).lower():
            # Try to extract channel ID from various formats
            import re
            channel_match = re.search(r'channel[_\s]*(?:id)?[:\s]*[\'"]?([^\'",\s]+)[\'"]?', str(item), re.IGNORECASE)
            if channel_match:
                channel_id = channel_match.group(1)
                break
    
    # Extract user input 
    user_input = ""
    for item in context:
        if item.startswith("user_input:") or item.startswith("task:") or item.startswith("content:"):
            user_input = item.split(":", 1)[1].strip()
            break
    
    # Extract user speech (non-command input)
    user_speech = ""
    if user_input and not user_input.startswith("$"):
        user_speech = user_input
    
    # Check for forced actions (testing)
    forced_action = None
    action_params = ""
    for item in context:
        if item.startswith("forced_action:"):
            forced_action = item.split(":", 1)[1]
        elif item.startswith("action_params:"):
            action_params = item.split(":", 1)[1]
    
    # Check for custom rationale
    custom_rationale = None
    for item in context:
        if item.startswith("custom_rationale:"):
            custom_rationale = item.split(":", 1)[1]
            break
    
    # Check for help request
    show_help = False
    for item in context:
        if item == "show_help_requested":
            show_help = True
            break
    
    # Determine action based on context
    # Initialize params with proper type annotation for 100% schema compliance
    params: ActionParams
    
    if forced_action:
        try:
            action = getattr(HandlerActionType, forced_action.upper())
            
            # Parse parameters based on action type
            if action == HandlerActionType.SPEAK:
                if action_params:
                    # Check if user wants to display context
                    if action_params.strip() == "$context":
                        # Display the full context
                        import json
                        context_display = "📋 **Full Context Display**\n\n"
                        context_display += "**Extracted Context Items:**\n"
                        for item in context:
                            context_display += f"• {item}\n"
                        
                        # Get the original messages if available
                        context_display += "\n**Original Messages:**\n"
                        for i, msg in enumerate(messages):
                            role = msg.get('role', 'unknown')
                            content = msg.get('content', '')
                            context_display += f"\n[{i}] {role}:\n{content}\n"
                        
                        params = SpeakParams(content=context_display, channel_context=create_channel_context(channel_id))
                    else:
                        params = SpeakParams(content=action_params, channel_context=create_channel_context(channel_id))
                else:
                    # Provide helpful error with valid format
                    error_msg = "❌ $speak requires content. Format: $speak <message>\nExample: $speak Hello world!\nSpecial: $speak $context (displays full context)"
                    params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                    
            elif action == HandlerActionType.MEMORIZE:
                if action_params:
                    # Try to parse node info from params
                    parts = action_params.split()
                    if len(parts) >= 1:
                        node_id = parts[0]
                        node_type = parts[1] if len(parts) > 1 else "CONCEPT"
                        scope = parts[2] if len(parts) > 2 else "LOCAL"
                        
                        # Validate and provide tooltips
                        valid_types = ["AGENT", "USER", "CHANNEL", "CONCEPT", "CONFIG"]
                        valid_scopes = ["LOCAL", "IDENTITY", "ENVIRONMENT", "COMMUNITY", "NETWORK"]
                        
                        if node_type.upper() not in valid_types:
                            error_msg = f"❌ Invalid node type '{node_type}'. Valid types: {', '.join(valid_types)}"
                            params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                            action = HandlerActionType.SPEAK
                        elif scope.upper() not in valid_scopes:
                            error_msg = f"❌ Invalid scope '{scope}'. Valid scopes: {', '.join(valid_scopes)}"
                            params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                            action = HandlerActionType.SPEAK
                        else:
                            params = MemorizeParams(
                                node=GraphNode(
                                    id=node_id,
                                    type=getattr(NodeType, node_type.upper()),
                                    scope=getattr(GraphScope, scope.upper()),
                                    attributes=GraphNodeAttributes(
                                        created_by="mock_llm"
                                    )
                                )
                            )
                    else:
                        error_msg = "❌ $memorize requires: <node_id> [type] [scope]\nExample: $memorize user123 USER LOCAL\nTypes: AGENT, USER, CHANNEL, CONCEPT, CONFIG\nScopes: LOCAL, IDENTITY, ENVIRONMENT, COMMUNITY, NETWORK"
                        params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                        action = HandlerActionType.SPEAK
                else:
                    error_msg = "❌ $memorize requires: <node_id> [type] [scope]\nExample: $memorize concept/weather CONCEPT LOCAL"
                    params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.RECALL:
                if action_params:
                    # Similar parsing as memorize
                    parts = action_params.split()
                    node_id = parts[0]
                    node_type = parts[1] if len(parts) > 1 else "CONCEPT"
                    scope = parts[2] if len(parts) > 2 else "LOCAL"
                    params = RecallParams(
                        node=GraphNode(
                            id=node_id,
                            type=getattr(NodeType, node_type.upper(), NodeType.CONCEPT),
                            scope=getattr(GraphScope, scope.upper(), GraphScope.LOCAL),
                            attributes=GraphNodeAttributes(
                                created_by="mock_llm"
                            )
                        )
                    )
                else:
                    error_msg = "❌ $recall requires: <node_id> [type] [scope]\nExample: $recall user123 USER LOCAL"
                    params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.PONDER:
                if action_params:
                    # Split by semicolon for multiple questions
                    questions = [q.strip() for q in action_params.split(';') if q.strip()]
                    params = PonderParams(questions=questions)
                else:
                    error_msg = "❌ $ponder requires questions. Format: $ponder <question1>; <question2>\nExample: $ponder What should I do next?; How can I help?"
                    params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.OBSERVE:
                parts = action_params.split() if action_params else []
                channel_id = parts[0] if len(parts) > 0 else ""
                active = parts[1].lower() == "true" if len(parts) > 1 else False
                channel_context = create_channel_context(channel_id) if channel_id else None
                params = ObserveParams(channel_context=channel_context, active=active)
                
            elif action == HandlerActionType.TOOL:
                if action_params:
                    parts = action_params.split(None, 1)
                    tool_name = parts[0]
                    tool_params = {}
                    
                    # Parse JSON-like parameters if provided
                    if len(parts) > 1:
                        try:
                            import json
                            tool_params = json.loads(parts[1])
                        except:
                            # Try simple key=value parsing
                            for pair in parts[1].split():
                                if '=' in pair:
                                    k, v = pair.split('=', 1)
                                    tool_params[k] = v
                    
                    params = ToolParams(name=tool_name, parameters=tool_params)
                else:
                    error_msg = "❌ $tool requires: <tool_name> [parameters]\nExample: $tool discord_delete_message channel_id=123 message_id=456\nAvailable tools: discord_delete_message, discord_timeout_user, list_files, read_file, etc."
                    params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.REJECT:
                if action_params:
                    params = RejectParams(reason=action_params)
                else:
                    error_msg = "❌ $reject requires a reason. Format: $reject <reason>\nExample: $reject This request violates ethical guidelines"
                    params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.DEFER:
                if action_params:
                    params = DeferParams(reason=action_params, defer_until=None)
                else:
                    error_msg = "❌ $defer requires a reason. Format: $defer <reason>\nExample: $defer I need more context to answer properly"
                    params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.FORGET:
                if action_params:
                    parts = action_params.split(None, 1)
                    if len(parts) >= 2:
                        node_id = parts[0]
                        reason = parts[1]
                        params = ForgetParams(
                            node=GraphNode(
                                id=node_id, 
                                type=NodeType.CONCEPT, 
                                scope=GraphScope.LOCAL,
                                attributes=GraphNodeAttributes(
                                    created_by="mock_llm"
                                )
                            ),
                            reason=reason
                        )
                    else:
                        error_msg = "❌ $forget requires: <node_id> <reason>\nExample: $forget user123 User requested data deletion"
                        params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                        action = HandlerActionType.SPEAK
                else:
                    error_msg = "❌ $forget requires: <node_id> <reason>"
                    params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.TASK_COMPLETE:
                # Mission-critical schema compliance with proper TaskCompleteParams
                params = TaskCompleteParams(completion_reason="Forced task completion via testing")
                
            else:
                # Unknown action
                params = SpeakParams(content=f"Unknown action: {forced_action}", channel_context=create_channel_context(channel_id))
                
        except AttributeError:
            # Invalid action type
            valid_actions = ['speak', 'recall', 'memorize', 'tool', 'observe', 'ponder', 
                           'defer', 'reject', 'forget', 'task_complete']
            error_msg = f"❌ Invalid action '{forced_action}'. Valid actions: {', '.join(valid_actions)}"
            action = HandlerActionType.SPEAK
            params = SpeakParams(content=error_msg, channel_context=create_channel_context(channel_id))
            
        # Include context pattern in rationale
        context_patterns = [item for item in context if item.startswith("forced_action:")]
        context_info = f" {context_patterns[0]}" if context_patterns else ""
        rationale = f"[MOCK LLM] Executing {forced_action} action from mock command{context_info}"
        
    if show_help:  # Changed from elif to if to handle help from anywhere
        action = HandlerActionType.SPEAK
        help_text = """📋 CIRIS Mock LLM Commands Help

🎛️ **Action Commands:**
• $speak <message>                - Send a message
• $recall <node_id> [type] [scope] - Recall from memory
• $memorize <node_id> [type] [scope] - Store in memory
• $tool <name> [params]           - Execute a tool
• $observe [channel_id] [active]  - Observe a channel
• $ponder <q1>; <q2>             - Ask questions
• $defer <reason>                 - Defer the task
• $reject <reason>                - Reject the request
• $forget <node_id> <reason>      - Forget memory
• $task_complete                  - Complete current task

🔧 **Testing & Debug Commands:**
• $test                          - Enable testing mode
• $error                         - Inject error conditions
• $rationale "custom text"       - Set custom rationale
• $context                       - Show full context
• $filter "regex"                - Filter context display
• $debug_dma                     - Show DMA details
• $debug_consciences              - Show conscience details
• $help                          - Show this help

📝 **Parameter Formats:**
• NodeType: AGENT, USER, CHANNEL, CONCEPT, CONFIG
• GraphScope: LOCAL, IDENTITY, ENVIRONMENT, COMMUNITY, NETWORK
• Tools: discord_delete_message, list_files, read_file, etc.

💡 **Examples:**
• $speak Hello world!
• $recall user123 USER LOCAL
• $tool read_file path=/tmp/test.txt
• $defer Need more information
• $ponder What should I do?; Is this ethical?

The mock LLM provides deterministic responses for testing CIRIS functionality offline."""
        params = SpeakParams(content=help_text, channel_context=create_channel_context(channel_id))
        rationale = "[MOCK LLM] Providing Mock LLM help documentation"
        
    # Removed the weird ? recall command - only $recall is supported
        
    elif user_speech:
        # Regular user input - always speak
        action = HandlerActionType.SPEAK
        params = SpeakParams(content=f"Mock response to: {user_speech}", channel_context=create_channel_context(channel_id))
        rationale = f"Responding to user: {user_speech}"
        
    else:
        # Step 1: Check if this is a follow-up thought by looking at the THOUGHT_TYPE in the system message
        is_followup = False
        
        # The first message should be the system message with covenant
        if messages and len(messages) > 0:
            first_msg = messages[0]
            if isinstance(first_msg, dict) and first_msg.get('role') == 'system':
                content = first_msg.get('content', '')
                # Check if this is a follow_up thought type
                if content.startswith('THOUGHT_TYPE=follow_up'):
                    is_followup = True
        
        if is_followup:
            # Follow-up thought → TASK_COMPLETE
            action = HandlerActionType.TASK_COMPLETE
            params = TaskCompleteParams(completion_reason="[MOCK LLM] Follow-up thought processing completed")
            rationale = "[MOCK LLM] Completing follow-up thought"
        else:
            # Step 2: For initial thoughts, check USER message for commands
            command_found = False
            
            # Look for the user message in the messages list
            for msg in messages:
                if isinstance(msg, dict) and msg.get('role') == 'user':
                    user_content = msg.get('content', '')
                    
                    # Extract the actual user input after "User @username said:" or similar patterns
                    import re
                    user_match = re.search(r'(?:User|@\w+)\s+(?:said|says?):\s*(.+)', user_content, re.IGNORECASE | re.DOTALL)
                    if user_match:
                        actual_user_input = user_match.group(1).strip()
                        
                        # Check if it starts with a command
                        if actual_user_input.startswith('$'):
                            # Parse the command
                            parts = actual_user_input.split(None, 1)
                            command = parts[0].lower()
                            command_args = parts[1] if len(parts) > 1 else ""
                            
                            # Handle specific commands
                            if command == '$speak':
                                action = HandlerActionType.SPEAK
                                params = SpeakParams(
                                    content=command_args if command_args else "[MOCK LLM] Hello!",
                                    channel_context=create_channel_context(channel_id)
                                )
                                rationale = f"[MOCK LLM] Executing speak command"
                                command_found = True
                                break
                            elif command == '$recall':
                                # Parse recall parameters
                                recall_parts = command_args.split()
                                node_id = recall_parts[0] if recall_parts else "test_node"
                                node_type = recall_parts[1] if len(recall_parts) > 1 else "CONCEPT"
                                scope = recall_parts[2] if len(recall_parts) > 2 else "LOCAL"
                                
                                params = RecallParams(
                                    node=GraphNode(
                                        id=node_id,
                                        type=getattr(NodeType, node_type.upper(), NodeType.CONCEPT),
                                        scope=getattr(GraphScope, scope.upper(), GraphScope.LOCAL),
                                        attributes=GraphNodeAttributes(
                                            created_by="mock_llm"
                                        )
                                    )
                                )
                                action = HandlerActionType.RECALL
                                rationale = f"[MOCK LLM] Recalling node {node_id}"
                                command_found = True
                                break
                            elif command == '$memorize':
                                # Parse memorize parameters
                                mem_parts = command_args.split()
                                node_id = mem_parts[0] if mem_parts else "test_node"
                                node_type = mem_parts[1] if len(mem_parts) > 1 else "CONCEPT"
                                scope = mem_parts[2] if len(mem_parts) > 2 else "LOCAL"
                                
                                params = MemorizeParams(
                                    node=GraphNode(
                                        id=node_id,
                                        type=getattr(NodeType, node_type.upper(), NodeType.CONCEPT),
                                        scope=getattr(GraphScope, scope.upper(), GraphScope.LOCAL),
                                        attributes=GraphNodeAttributes(
                                            created_by="mock_llm"
                                        )
                                    )
                                )
                                action = HandlerActionType.MEMORIZE
                                rationale = f"[MOCK LLM] Memorizing node {node_id}"
                                command_found = True
                                break
                            elif command == '$ponder':
                                questions = command_args.split(';') if command_args else ["What should I do?"]
                                params = PonderParams(questions=[q.strip() for q in questions if q.strip()])
                                action = HandlerActionType.PONDER
                                rationale = "[MOCK LLM] Pondering questions"
                                command_found = True
                                break
                            elif command == '$observe':
                                obs_parts = command_args.split()
                                obs_channel = obs_parts[0] if obs_parts else channel_id
                                active = obs_parts[1].lower() == 'true' if len(obs_parts) > 1 else False
                                
                                params = ObserveParams(
                                    channel_context=create_channel_context(obs_channel),
                                    active=active
                                )
                                action = HandlerActionType.OBSERVE
                                rationale = f"[MOCK LLM] Observing channel {obs_channel}"
                                command_found = True
                                break
                            elif command == '$tool':
                                tool_parts = command_args.split(None, 1)
                                tool_name = tool_parts[0] if tool_parts else "unknown_tool"
                                tool_params = {}
                                
                                if len(tool_parts) > 1:
                                    # Try to parse JSON params
                                    try:
                                        import json
                                        tool_params = json.loads(tool_parts[1])
                                    except:
                                        # Simple key=value parsing
                                        for pair in tool_parts[1].split():
                                            if '=' in pair:
                                                k, v = pair.split('=', 1)
                                                tool_params[k] = v
                                
                                params = ToolParams(name=tool_name, parameters=tool_params)
                                action = HandlerActionType.TOOL
                                rationale = f"[MOCK LLM] Executing tool {tool_name}"
                                command_found = True
                                break
                            elif command == '$defer':
                                params = DeferParams(reason=command_args if command_args else "Need more information", defer_until=None)
                                action = HandlerActionType.DEFER
                                rationale = "[MOCK LLM] Deferring task"
                                command_found = True
                                break
                            elif command == '$reject':
                                params = RejectParams(reason=command_args if command_args else "Cannot fulfill request")
                                action = HandlerActionType.REJECT
                                rationale = "[MOCK LLM] Rejecting request"
                                command_found = True
                                break
                            elif command == '$forget':
                                forget_parts = command_args.split(None, 1)
                                if len(forget_parts) >= 2:
                                    node_id = forget_parts[0]
                                    reason = forget_parts[1]
                                    params = ForgetParams(
                                        node=GraphNode(
                                            id=node_id, 
                                            type=NodeType.CONCEPT, 
                                            scope=GraphScope.LOCAL,
                                            attributes=GraphNodeAttributes(
                                                created_by="mock_llm"
                                            )
                                        ),
                                        reason=reason
                                    )
                                    action = HandlerActionType.FORGET
                                    rationale = f"[MOCK LLM] Forgetting node {node_id}"
                                    command_found = True
                                    break
                            elif command == '$task_complete':
                                params = TaskCompleteParams(completion_reason="[MOCK LLM] Task completed via command")
                                action = HandlerActionType.TASK_COMPLETE
                                rationale = "[MOCK LLM] Completing task"
                                command_found = True
                                break
                            elif command == '$help':
                                # Show help
                                show_help = True
                                break
            
            if show_help:
                # Return to the help handler below
                pass
            elif not command_found:
                # Default: new task → SPEAK
                action = HandlerActionType.SPEAK
                params = SpeakParams(content="[MOCK LLM] Hello! How can I help you?", channel_context=create_channel_context(channel_id))
                rationale = "[MOCK LLM] Default speak action for new task"
    
    # Use custom rationale if provided, otherwise use the generated rationale
    final_rationale = custom_rationale if custom_rationale else rationale
    
    # Store action parameters directly as a dict
    if params:
        action_params_dict = params.model_dump() if hasattr(params, 'model_dump') else params
    else:
        action_params_dict = None
    
    result = ActionSelectionDMAResult(
        selected_action=action,
        action_parameters=action_params_dict,  # Store parameters directly
        rationale=final_rationale
    )
    
    # Return structured result directly - instructor will handle it
    return result
