# Protocol-facing mock responses for ActionSelectionResult and related types
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import (
    SpeakParams, MemorizeParams, RecallParams, PonderParams,
    ObserveParams, ToolParams, RejectParams, DeferParams,
    ForgetParams
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

def action_selection(context=None):
    """Mock ActionSelectionResult with passing values and protocol-compliant types."""
    context = context or []
    
    # Extract messages from context if available
    messages = []
    for item in context:
        if item.startswith("__messages__:"):
            import json
            try:
                messages = json.loads(item.split(":", 1)[1])
            except:
                pass
            break
    
    # Extract user speech for appropriate response
    user_speech = ""
    for item in context:
        if item.startswith("echo_user_speech:"):
            user_speech = item.split(":", 1)[1]
            break
    
    # Extract memory query for recall action
    memory_query = ""
    for item in context:
        if item.startswith("echo_memory_query:"):
            memory_query = item.split(":", 1)[1]
            break
    
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
                        
                        params = SpeakParams(content=context_display, channel_id="test")
                    else:
                        params = SpeakParams(content=action_params, channel_id="test")
                else:
                    # Provide helpful error with valid format
                    error_msg = "❌ $speak requires content. Format: $speak <message>\nExample: $speak Hello world!\nSpecial: $speak $context (displays full context)"
                    params = SpeakParams(content=error_msg, channel_id="test")
                    
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
                            params = SpeakParams(content=error_msg, channel_id="test")
                            action = HandlerActionType.SPEAK
                        elif scope.upper() not in valid_scopes:
                            error_msg = f"❌ Invalid scope '{scope}'. Valid scopes: {', '.join(valid_scopes)}"
                            params = SpeakParams(content=error_msg, channel_id="test")
                            action = HandlerActionType.SPEAK
                        else:
                            params = MemorizeParams(
                                node=GraphNode(
                                    id=node_id,
                                    type=getattr(NodeType, node_type.upper()),
                                    scope=getattr(GraphScope, scope.upper())
                                )
                            )
                    else:
                        error_msg = "❌ $memorize requires: <node_id> [type] [scope]\nExample: $memorize user123 USER LOCAL\nTypes: AGENT, USER, CHANNEL, CONCEPT, CONFIG\nScopes: LOCAL, IDENTITY, ENVIRONMENT, COMMUNITY, NETWORK"
                        params = SpeakParams(content=error_msg, channel_id="test")
                        action = HandlerActionType.SPEAK
                else:
                    error_msg = "❌ $memorize requires: <node_id> [type] [scope]\nExample: $memorize concept/weather CONCEPT LOCAL"
                    params = SpeakParams(content=error_msg, channel_id="test")
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
                            scope=getattr(GraphScope, scope.upper(), GraphScope.LOCAL)
                        )
                    )
                else:
                    error_msg = "❌ $recall requires: <node_id> [type] [scope]\nExample: $recall user123 USER LOCAL"
                    params = SpeakParams(content=error_msg, channel_id="test")
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.PONDER:
                if action_params:
                    # Split by semicolon for multiple questions
                    questions = [q.strip() for q in action_params.split(';') if q.strip()]
                    params = PonderParams(questions=questions)
                else:
                    error_msg = "❌ $ponder requires questions. Format: $ponder <question1>; <question2>\nExample: $ponder What should I do next?; How can I help?"
                    params = SpeakParams(content=error_msg, channel_id="test")
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.OBSERVE:
                parts = action_params.split() if action_params else []
                channel_id = parts[0] if len(parts) > 0 else None
                active = parts[1].lower() == "true" if len(parts) > 1 else False
                params = ObserveParams(channel_id=channel_id, active=active)
                
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
                    params = SpeakParams(content=error_msg, channel_id="test")
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.REJECT:
                if action_params:
                    params = RejectParams(reason=action_params)
                else:
                    error_msg = "❌ $reject requires a reason. Format: $reject <reason>\nExample: $reject This request violates ethical guidelines"
                    params = SpeakParams(content=error_msg, channel_id="test")
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.DEFER:
                if action_params:
                    params = DeferParams(reason=action_params)
                else:
                    error_msg = "❌ $defer requires a reason. Format: $defer <reason>\nExample: $defer I need more context to answer properly"
                    params = SpeakParams(content=error_msg, channel_id="test")
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.FORGET:
                if action_params:
                    parts = action_params.split(None, 1)
                    if len(parts) >= 2:
                        node_id = parts[0]
                        reason = parts[1]
                        params = ForgetParams(
                            node=GraphNode(id=node_id, type=NodeType.CONCEPT, scope=GraphScope.LOCAL),
                            reason=reason
                        )
                    else:
                        error_msg = "❌ $forget requires: <node_id> <reason>\nExample: $forget user123 User requested data deletion"
                        params = SpeakParams(content=error_msg, channel_id="test")
                        action = HandlerActionType.SPEAK
                else:
                    error_msg = "❌ $forget requires: <node_id> <reason>"
                    params = SpeakParams(content=error_msg, channel_id="test")
                    action = HandlerActionType.SPEAK
                    
            elif action == HandlerActionType.TASK_COMPLETE:
                # No parameters needed
                params = {}
                
            else:
                # Unknown action
                params = SpeakParams(content=f"Unknown action: {forced_action}", channel_id="test")
                
        except AttributeError:
            # Invalid action type
            valid_actions = ['speak', 'recall', 'memorize', 'tool', 'observe', 'ponder', 
                           'defer', 'reject', 'forget', 'task_complete']
            error_msg = f"❌ Invalid action '{forced_action}'. Valid actions: {', '.join(valid_actions)}"
            action = HandlerActionType.SPEAK
            params = SpeakParams(content=error_msg, channel_id="test")
            
        # Include context pattern in rationale
        context_patterns = [item for item in context if item.startswith("forced_action:")]
        context_info = f" {context_patterns[0]}" if context_patterns else ""
        rationale = f"Executing {forced_action} action from mock command{context_info}"
        
    elif show_help:
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
• $debug_guardrails              - Show guardrail details
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
        params = SpeakParams(content=help_text, channel_id="test")
        rationale = "Providing Mock LLM help documentation"
        
    elif user_speech:
        action = HandlerActionType.SPEAK
        params = SpeakParams(content=f"Mock response to: {user_speech}", channel_id="test")
        # Include context pattern in rationale
        context_patterns = [item for item in context if item.startswith("echo_user_speech:")]
        context_info = f" {context_patterns[0]}" if context_patterns else ""
        rationale = f"Responding to user speech: {user_speech}{context_info}"
        
    elif memory_query:
        action = HandlerActionType.RECALL
        params = RecallParams(
            node=GraphNode(id=f"query/{memory_query}", type=NodeType.CONCEPT, scope=GraphScope.LOCAL)
        )
        # Include context pattern in rationale  
        context_patterns = [item for item in context if item.startswith("echo_memory_query:")]
        context_info = f" {context_patterns[0]}" if context_patterns else ""
        rationale = f"Recalling memory for: {memory_query}{context_info}"
        
    else:
        # Default ponder action
        action = HandlerActionType.PONDER
        params = PonderParams(questions=["What should I do next?"])
        rationale = "No specific context detected, defaulting to ponder action."
    
    # Use custom rationale if provided, otherwise use the generated rationale
    final_rationale = custom_rationale if custom_rationale else rationale
    
    result = ActionSelectionResult(
        selected_action=action,
        action_parameters=params,
        rationale=final_rationale,
        confidence=0.9
    )
    object.__setattr__(result, 'choices', [result])
    object.__setattr__(result, 'finish_reason', 'stop')
    object.__setattr__(result, '_raw_response', 'mock')
    return result