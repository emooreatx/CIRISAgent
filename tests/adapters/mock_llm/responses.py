import re
import json
from types import SimpleNamespace
from typing import Any, List, Dict, Optional

from ciris_engine.schemas.dma_results_v1 import (
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionResult,
)
from ciris_engine.schemas.feedback_schemas_v1 import (
    OptimizationVetoResult,
    EpistemicHumilityResult,
)
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.schemas.action_params_v1 import (
    PonderParams, MemorizeParams, SpeakParams, RecallParams, 
    ObserveParams, RejectParams, DeferParams
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope


# Configuration for context echoing and testing behaviors
class MockLLMConfig:
    """Configuration for mock LLM behavior."""
    
    def __init__(self):
        # Regex patterns to match in messages for context echoing
        self.context_patterns = {
            r'user.*says?.*"([^"]+)"': lambda m: f"echo_user_speech:{m.group(1)}",
            r'thought.*content.*"([^"]+)"': lambda m: f"echo_thought:{m.group(1)}",
            r'channel.*(?:id|ID).*[\'"]([^\'"]+)[\'"]': lambda m: f"echo_channel:{m.group(1)}",
            r'memory.*search.*[\'"]([^\'"]+)[\'"]': lambda m: f"echo_memory_query:{m.group(1)}",
            r'domain.*[\'"]([^\'"]+)[\'"]': lambda m: f"echo_domain:{m.group(1)}",
            # Capture full message content as thought content for wakeup detection
            r'(You are CIRISAgent.*)': lambda m: f"echo_thought:{m.group(1)}",
            r'(Your internal state.*)': lambda m: f"echo_thought:{m.group(1)}",
            r'(You are robust.*)': lambda m: f"echo_thought:{m.group(1)}",
            r'(You recognize your incompleteness.*)': lambda m: f"echo_thought:{m.group(1)}",
            r'(You are grateful.*)': lambda m: f"echo_thought:{m.group(1)}",
        }
        
        # Testing flags that can be set via special markers in messages
        self.testing_mode = False
        self.force_action = None  # Force specific action selection
        self.inject_error = False  # Inject error conditions
        self.custom_rationale = None  # Custom rationale text


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
    
    # Check for testing flags
    if "MOCK_TEST_MODE" in full_content:
        _mock_config.testing_mode = True
        context_items.append("testing_mode_enabled")
    
    if match := re.search(r'MOCK_FORCE_ACTION:(\w+)', full_content):
        _mock_config.force_action = match.group(1)
        context_items.append(f"forced_action:{match.group(1)}")
    
    if "MOCK_INJECT_ERROR" in full_content:
        _mock_config.inject_error = True
        context_items.append("error_injection_enabled")
    
    if match := re.search(r'MOCK_RATIONALE:"([^"]+)"', full_content):
        _mock_config.custom_rationale = match.group(1)
        context_items.append(f"custom_rationale:{match.group(1)}")
    
    return context_items


def _attach_extras(obj: Any) -> Any:
    """Mimic instructor extra attributes expected on responses."""
    import json
    # Convert the object to JSON to simulate what a real LLM would return
    try:
        if hasattr(obj, 'model_dump'):
            # Pydantic object
            content_json = json.dumps(obj.model_dump())
        else:
            # Fallback for other objects
            content_json = json.dumps(obj.__dict__ if hasattr(obj, '__dict__') else str(obj))
    except Exception:
        content_json = "{}"
    
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
    
    # Extract thought content for ethical analysis
    thought_content = ""
    for item in context:
        if item.startswith("echo_thought:"):
            thought_content = item.split(":", 1)[1]
            break
    
    # Determine if this is a wakeup thought or user interaction
    is_wakeup = any("wakeup" in item.lower() or "verify" in item.lower() or "validate" in item.lower() 
                   for item in context) or "WAKEUP" in thought_content.upper()
    
    is_user_question = any("echo_user_speech:" in item for item in context) or "?" in thought_content
    
    # Check for error injection
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
        
        # Provide CIRIS-aligned ethical evaluation
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
    
    return _attach_extras(
        EthicalDMAResult(alignment_check=alignment_check, decision=decision, rationale=rationale)
    )


def cs_dma(context: List[str] = None) -> CSDMAResult:
    context = context or []
    
    # Extract thought content for plausibility analysis
    thought_content = ""
    for item in context:
        if item.startswith("echo_thought:"):
            thought_content = item.split(":", 1)[1]
            break
    
    # Extract user speech for analysis
    user_speech = ""
    for item in context:
        if item.startswith("echo_user_speech:"):
            user_speech = item.split(":", 1)[1]
            break
    
    # Determine context type for plausibility scoring
    is_wakeup = any("wakeup" in item.lower() or "verify" in item.lower() 
                   for item in context) or "WAKEUP" in thought_content.upper()
    is_user_interaction = bool(user_speech) or "?" in thought_content
    is_memory_operation = any("recall" in item.lower() or "memory" in item.lower() for item in context)
    
    # Check for error injection
    if _mock_config.inject_error:
        score = 0.3
        flags = ["plausibility_concern", "requires_clarification"] + context
        reasoning = "Injected low plausibility for testing error handling paths."
    else:
        # High plausibility for standard operations
        if is_wakeup:
            score = 0.95
            flags = ["wakeup_ritual", "system_initialization"]
            reasoning = "Wakeup ritual thoughts are inherently plausible and necessary for agent initialization. High confidence in procedural integrity."
        elif is_user_interaction:
            score = 0.92
            flags = ["human_interaction", "conversational"]
            reasoning = f"User interaction '{user_speech or thought_content[:50]}' is plausible conversational content. Natural dialogue pattern detected."
        elif is_memory_operation:
            score = 0.88
            flags = ["memory_operation", "cognitive_function"]
            reasoning = "Memory operations are standard cognitive functions with high plausibility for autonomous agents."
        else:
            score = 0.85
            flags = ["general_processing"]
            reasoning = "General thought processing within normal parameters. No physical impossibilities or logical contradictions detected."
    
    return _attach_extras(CSDMAResult(plausibility_score=score, flags=flags, reasoning=reasoning))


def ds_dma(context: List[str] = None) -> DSDMAResult:
    context = context or []
    domain = next((item.split(':')[1] for item in context if item.startswith('echo_domain:')), "mock")
    reasoning = f"Mock domain-specific evaluation. Context: {', '.join(context)}" if context else "Mock domain-specific evaluation."
    
    score = 0.2 if _mock_config.inject_error else 0.9
    flags = ["mock_domain_flag"] + context if _mock_config.inject_error else context
    
    return _attach_extras(DSDMAResult(domain=domain, score=score, flags=flags, reasoning=reasoning))


def ds_dma_llm_output(context: List[str] = None) -> BaseDSDMA.LLMOutputForDSDMA:
    context = context or []
    reasoning = f"Mock DSDMA LLM output. Context: {', '.join(context)}" if context else "Mock DSDMA LLM output."
    
    score = 0.1 if _mock_config.inject_error else 1.0
    action = "halt" if _mock_config.inject_error else "proceed"
    flags = ["mock_llm_flag"] + context if _mock_config.inject_error else context
    
    result = BaseDSDMA.LLMOutputForDSDMA(
        score=score,
        recommended_action=action,
        flags=flags,
        reasoning=reasoning,
    )
    return _attach_extras(result)


def optimization_veto(context: List[str] = None) -> OptimizationVetoResult:
    context = context or []
    justification = f"Mock optimization veto. Context: {', '.join(context)}" if context else "Mock optimization veto."
    
    return _attach_extras(
        OptimizationVetoResult(
            decision="proceed",
            justification=justification,
            entropy_reduction_ratio=0.0,
            affected_values=context,
            confidence=1.0,
        )
    )


def epistemic_humility(context: List[str] = None) -> EpistemicHumilityResult:
    context = context or []
    justification = f"Mock epistemic humility. Context: {', '.join(context)}" if context else "Mock epistemic humility."
    
    return _attach_extras(
        EpistemicHumilityResult(
            epistemic_certainty="high",
            identified_uncertainties=context,
            reflective_justification=justification,
            recommended_action="proceed",
        )
    )


def action_selection(context: List[str] = None) -> ActionSelectionResult:
    context = context or []
    
    # Check for forced action first
    if _mock_config.force_action:
        try:
            selected_action = HandlerActionType(_mock_config.force_action.lower())
            rationale = f"Forced action: {_mock_config.force_action}"
        except ValueError:
            selected_action = HandlerActionType.SPEAK
            rationale = f"Invalid forced action '{_mock_config.force_action}', defaulting to SPEAK"
    else:
        # Default to SPEAK with information about what we received
        selected_action = HandlerActionType.SPEAK
        rationale = "Mock LLM default response"
    
    # Special case: follow-up thoughts should complete tasks
    context_str = " ".join(context).lower()
    if "follow" in context_str and "up" in context_str:
        selected_action = HandlerActionType.TASK_COMPLETE
        action_parameters = {}
        rationale = "Follow-up thought detected - completing task"
    else:
        # Default SPEAK action with simple content about what we received
        content_info = f"Mock LLM received: {', '.join(context[:2])}" if context else "Mock LLM response"
        if len(context) > 2:
            content_info += f" (+{len(context)-2} more items)"
        
        action_parameters = SpeakParams(
            content=content_info,
            channel_id="cli"
        ).model_dump(mode="json")
    
    # Use custom rationale if provided
    if _mock_config.custom_rationale:
        rationale = _mock_config.custom_rationale
    
    return _attach_extras(
        ActionSelectionResult(
            selected_action=selected_action,
            action_parameters=action_parameters,
            rationale=rationale,
            confidence=0.95,
            raw_llm_response=f"Mock LLM action selection: {selected_action.value}",
        )
    )


def entropy() -> EntropyResult:
    return _attach_extras(EntropyResult(entropy=0.1))


def coherence() -> CoherenceResult:
    return _attach_extras(CoherenceResult(coherence=0.9))


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


def create_response(model: Any, messages: List[Dict[str, Any]] = None, **kwargs) -> Any:
    """Create a mock LLM response with context analysis."""
    messages = messages or []
    
    # Extract context from messages
    context = extract_context_from_messages(messages)
    
    # Get the appropriate handler
    handler = _RESPONSE_MAP.get(model)
    if handler:
        # Check if handler accepts context parameter
        import inspect
        sig = inspect.signature(handler)
        if 'context' in sig.parameters:
            return handler(context=context)
        else:
            return handler()
    
    # Default response with context echoing
    context_echo = f"Context: {', '.join(context)}" if context else "No context detected"
    return _attach_extras(SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=f"OK - {context_echo}"))]))
