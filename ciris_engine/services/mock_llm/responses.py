import re
import json
import logging
from types import SimpleNamespace
from typing import Any, List, Dict, Optional

from ciris_engine.schemas.dma_results_v1 import (
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionResult,
)

logger = logging.getLogger(__name__)
from ciris_engine.schemas.feedback_schemas_v1 import (
    OptimizationVetoResult,
    EpistemicHumilityResult,
    FeedbackType,
)
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.schemas.action_params_v1 import (
    PonderParams, MemorizeParams, SpeakParams, RecallParams, 
    ObserveParams, RejectParams, DeferParams
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope


class MockLLMConfig:
    """Configuration for mock LLM behavior."""
    
    def __init__(self):
        # Regex patterns to match in messages for context echoing
        self.context_patterns = {
            r'user.*?says?.*?"([^"]+)"': lambda m: f"echo_user_speech:{m.group(1)}",
            r'thought.*content.*"([^"]+)"': lambda m: f"echo_thought:{m.group(1)}",
            r'channel.*?[\'"]([^\'"]+)[\'"]': lambda m: f"echo_channel:{m.group(1)}",
            r'channel\s+([#@]?[\w-]+)': lambda m: f"echo_channel:{m.group(1)}",
            r'(?:search.*memory|memory.*search).*[\'"]([^\'"]+)[\'"]': lambda m: f"echo_memory_query:{m.group(1)}",
            r'domain.*[\'"]([^\'"]+)[\'"]': lambda m: f"echo_domain:{m.group(1)}",
            # Capture wakeup ritual content
            r'(You are CIRISAgent.*?)(?:\.|$)': lambda m: f"echo_wakeup:VERIFY_IDENTITY",
            r'(Your internal state.*?)(?:\.|$)': lambda m: f"echo_wakeup:VALIDATE_INTEGRITY",
            # Capture startup patterns
            r'validate identity': lambda m: f"VERIFY_IDENTITY",
            r'check integrity': lambda m: f"VALIDATE_INTEGRITY", 
            r'evaluate resilience': lambda m: f"EVALUATE_RESILIENCE",
            r'accept incompleteness': lambda m: f"ACCEPT_INCOMPLETENESS",
            r'express gratitude': lambda m: f"EXPRESS_GRATITUDE", 
            r'(You are robust.*?)(?:\.|$)': lambda m: f"echo_wakeup:EVALUATE_RESILIENCE",
            r'(You recognize your incompleteness.*?)(?:\.|$)': lambda m: f"echo_wakeup:ACCEPT_INCOMPLETENESS",
            r'(You are grateful.*?)(?:\.|$)': lambda m: f"echo_wakeup:EXPRESS_GRATITUDE",
            # Catch-all for any content
            r'(.+)': lambda m: f"echo_content:{m.group(1)[:100]}"
        }
        
        # Testing flags that can be set via special markers in messages
        self.testing_mode = False
        self.force_action = None  # Force specific action selection
        self.inject_error = False  # Inject error conditions
        self.custom_rationale = None  # Custom rationale text
        self.echo_context = False  # Echo full context in responses
        self.filter_pattern = None  # Regex filter for context display
        self.debug_dma = False  # Show DMA evaluation details
        self.debug_guardrails = False  # Show guardrail processing details
        self.show_help = False  # Show help documentation


# Global config instance
_mock_config = MockLLMConfig()


def set_mock_config(**kwargs):
    """Update mock LLM configuration."""
    global _mock_config
    for key, value in kwargs.items():
        if hasattr(_mock_config, key):
            setattr(_mock_config, key, value)


def extract_context_from_messages(messages: List[Dict[str, Any]]) -> List[str]:
    """Extract context information from messages using regex patterns."""
    context_items = []
    
    # Store original messages for $context display
    import json
    context_items.append(f"__messages__:{json.dumps(messages)}")
    
    # Look for actual thought content in messages
    actual_thought_content = ""
    for msg in messages:
        content = ""
        if isinstance(msg, dict) and 'content' in msg:
            content = msg['content']
        elif hasattr(msg, 'content'):
            content = msg.content
            
        # Look for the actual thought content pattern
        if "Original Thought:" in content:
            # Extract the thought after "Original Thought:" 
            thought_match = re.search(r'Original Thought:\s*"([^"]+)"', content)
            if thought_match:
                actual_thought_content = thought_match.group(1)
                # Add this to context items so it gets processed properly
                context_items.append(f"echo_thought:{actual_thought_content}")
                break
    
    # Combine all message content
    full_content = ""
    for msg in messages:
        if isinstance(msg, dict) and 'content' in msg:
            full_content += f" {msg['content']}"
        elif hasattr(msg, 'content'):
            full_content += f" {msg.content}"
    
    # Apply regex patterns
    for pattern, extractor in _mock_config.context_patterns.items():
        matches = re.finditer(pattern, full_content, re.IGNORECASE)
        for match in matches:
            try:
                context_items.append(extractor(match))
            except Exception:
                continue
    
    # Check for testing flags and commands with new $ syntax
    if "$test" in full_content:
        _mock_config.testing_mode = True
        context_items.append("testing_mode_enabled")
    
    # Direct action commands (e.g., $speak, $recall, etc.)
    action_match = re.search(r'\$(\w+)(?:\s+(.+?))?(?=\$|$)', full_content)
    if action_match:
        action = action_match.group(1).lower()
        params = action_match.group(2) if action_match.group(2) else ""
        
        # Validate action and store it
        valid_actions = ['speak', 'recall', 'memorize', 'tool', 'observe', 'ponder', 
                        'defer', 'reject', 'forget', 'task_complete']
        if action in valid_actions:
            _mock_config.force_action = action
            context_items.append(f"forced_action:{action}")
            if params:
                context_items.append(f"action_params:{params}")
    
    if "$error" in full_content:
        _mock_config.inject_error = True
        context_items.append("error_injection_enabled")
    
    if match := re.search(r'\$rationale\s+"([^"]+)"', full_content):
        _mock_config.custom_rationale = match.group(1)
        context_items.append(f"custom_rationale:{match.group(1)}")
    
    if "$context" in full_content:
        _mock_config.echo_context = True
        context_items.append("echo_context_enabled")
    
    if match := re.search(r'\$filter\s+"([^"]+)"', full_content):
        _mock_config.filter_pattern = match.group(1)
        context_items.append(f"filter_pattern:{match.group(1)}")
    
    if "$debug_dma" in full_content:
        _mock_config.debug_dma = True
        context_items.append("debug_dma_enabled")
        
    if "$debug_guardrails" in full_content:
        _mock_config.debug_guardrails = True
        context_items.append("debug_guardrails_enabled")
    
    if "$help" in full_content:
        _mock_config.show_help = True
        context_items.append("show_help_requested")
    
    return context_items


def _attach_extras(obj: Any) -> Any:
    """Mimic instructor extra attributes expected on responses."""
    import json
    try:
        if hasattr(obj, 'model_dump'):
            content_json = json.dumps(obj.model_dump())
        else:
            content_json = json.dumps(obj.__dict__ if hasattr(obj, '__dict__') else str(obj))
    except Exception as e:
        logger.error(f"Failed to serialize object {type(obj)}: {e}")
        logger.error(f"Object content: {obj}")
        content_json = '{"error": "serialization_failed"}'
    
    object.__setattr__(obj, "finish_reason", "stop")
    object.__setattr__(obj, "_raw_response", {"mock": True})
    object.__setattr__(obj, "choices", [SimpleNamespace(
        finish_reason="stop",
        message=SimpleNamespace(role="assistant", content=content_json)
    )])
    object.__setattr__(obj, "usage", SimpleNamespace(total_tokens=42))
    return obj


def ethical_dma(context: List[str] = None) -> EthicalDMAResult:
    context = context or []
    
    thought_content = ""
    for item in context:
        if item.startswith("echo_thought:"):
            thought_content = item.split(":", 1)[1]
            break
    
    is_wakeup = any("wakeup" in item.lower() or "verify" in item.lower() or "validate" in item.lower() 
                   for item in context) or "WAKEUP" in thought_content.upper()
    
    is_user_question = any("echo_user_speech:" in item for item in context) or "?" in thought_content
    
    if _mock_config.inject_error:
        decision = "defer"
        alignment_check = {
            "ethical_uncertainty": True, 
            "context": context,
            "requires_wisdom_based_deferral": True
        }
        rationale = "Injected ethical uncertainty for testing purposes."
    else:
        decision = "proceed"
        
        if is_wakeup:
            alignment_check = {
                "beneficence": True,
                "non_maleficence": True, 
                "integrity": True,
                "autonomy_respect": True,
                "justice": True,
                "transparency": True,
                "covenant_alignment": "wakeup_ritual_proceeding"
            }
            rationale = "Wakeup ritual thought aligns with CIRIS covenant principles. Promoting agent integrity and identity verification as required by Meta-Goal M-1."
        elif is_user_question:
            alignment_check = {
                "beneficence": True,
                "non_maleficence": True,
                "integrity": True, 
                "autonomy_respect": True,
                "transparency": True,
                "promotes_flourishing": True
            }
            rationale = "User interaction promotes beneficial dialogue and respects human autonomy. Response will be honest, helpful, and transparent per CIRIS principles."
        else:
            alignment_check = {
                "beneficence": True,
                "non_maleficence": True,
                "integrity": True,
                "general_alignment": "proceeding_with_caution"
            }
            rationale = "General thought processing aligns with ethical guidelines. No contraindications to CIRIS covenant principles detected."
    
    decision_param = str(decision)  # Ensure decision is always a string
    return _attach_extras(
        EthicalDMAResult(alignment_check=alignment_check, decision=decision_param, rationale=str(rationale))
    )


def cs_dma(context: List[str] = None) -> CSDMAResult:
    context = context or []
    thought_content = ""
    for item in context:
        if item.startswith("echo_thought:"):
            thought_content = item.split(":", 1)[1]
            break
    user_speech = ""
    for item in context:
        if item.startswith("echo_user_speech:"):
            user_speech = item.split(":", 1)[1]
            break
    is_wakeup = any("wakeup" in item.lower() or "verify" in item.lower() 
                   for item in context) or "WAKEUP" in thought_content.upper()
    is_user_interaction = bool(user_speech) or "?" in thought_content
    is_memory_operation = any("recall" in item.lower() or "memory" in item.lower() for item in context)
    if _mock_config.inject_error:
        score = 0.3
        flags = ["plausibility_concern", "requires_clarification", "mock_flag"] + context
        reasoning = "Injected low plausibility for testing error handling paths."
    else:
        score = 0.9  # Always passing value
        if is_wakeup:
            flags = ["wakeup_ritual", "system_initialization"]
            reasoning = "Wakeup ritual thoughts are inherently plausible and necessary for agent initialization. High confidence in procedural integrity."
        elif is_user_interaction:
            flags = ["human_interaction", "conversational"]
            reasoning = f"User interaction '{user_speech or thought_content[:50]}' is plausible conversational content. Natural dialogue pattern detected."
        elif is_memory_operation:
            flags = ["memory_operation", "cognitive_function"]
            reasoning = "Memory operations are standard cognitive functions with high plausibility for autonomous agents."
        else:
            flags = ["general_processing"]
            reasoning = "General thought processing within normal parameters. No physical impossibilities or logical contradictions detected."
    
    return _attach_extras(CSDMAResult(plausibility_score=score, flags=flags, reasoning=reasoning))


def ds_dma(context: List[str] = None) -> DSDMAResult:
    context = context or []
    domain_val = next((item.split(':')[1] for item in context if item.startswith('echo_domain:')), "mock")
    reasoning = f"Mock domain-specific evaluation. Context: {', '.join(context)}" if context else "Mock domain-specific evaluation."
    score_val = 0.9
    flags = ["mock_domain_flag"] + context if _mock_config.inject_error else context
    return _attach_extras(DSDMAResult(domain=domain_val, score=score_val, flags=flags, reasoning=reasoning))


def ds_dma_llm_output(context: List[str] = None) -> BaseDSDMA.LLMOutputForDSDMA:
    context = context or []
    reasoning = f"Mock DSDMA LLM output. Context: {', '.join(context)}" if context else "Mock DSDMA LLM output."
    score_val = 0.9
    result = BaseDSDMA.LLMOutputForDSDMA(
        score=score_val,
        recommended_action="proceed",
        flags=context,
        reasoning=reasoning,
    )
    return _attach_extras(result)

from .responses_action_selection import action_selection
from .responses_feedback import optimization_veto, epistemic_humility
from .responses_epistemic import entropy, coherence

_RESPONSE_MAP = {
    EthicalDMAResult: ethical_dma,
    CSDMAResult: cs_dma,
    DSDMAResult: ds_dma,
    BaseDSDMA.LLMOutputForDSDMA: ds_dma_llm_output,
    OptimizationVetoResult: optimization_veto,
    EpistemicHumilityResult: epistemic_humility,
    ActionSelectionResult: action_selection,
    EntropyResult: entropy,
    CoherenceResult: coherence,
}

def create_response(response_model: Any, messages: List[Dict[str, Any]] = None, **kwargs) -> Any:
    """Create a mock LLM response with context analysis."""
    messages = messages or []
    # Extract context from messages
    context = extract_context_from_messages(messages)
    # Debug for any structured calls
    logger.debug(f"Request for: {response_model}")
    # Get the appropriate handler
    handler = _RESPONSE_MAP.get(response_model)
    if handler:
        logger.debug(f"Found handler: {handler.__name__}")
        import inspect
        sig = inspect.signature(handler)
        if 'context' in sig.parameters:
            result = handler(context=context)
        else:
            result = handler()
        logger.debug(f"Handler returned: {type(result)}")
        return result
    # Handle None response models - these should not happen in a properly structured system
    if response_model is None:
        logger.warning("Received None response_model - this indicates unstructured LLM call")
        logger.warning(f"Context: {context}")
        return SimpleNamespace(
            finish_reason="stop",
            _raw_response={"mock": True},
            choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(
                    role="assistant", 
                    content='{"status": "unstructured_call_detected"}'
                )
            )],
            usage=SimpleNamespace(total_tokens=42)
        )
    # Default response with context echoing
    context_echo = f"Context: {', '.join(context)}" if context else "No context detected"
    return _attach_extras(SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=f"OK - {context_echo}"))]))
