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
from ciris_engine.schemas.action_params_v1 import PonderParams, MemorizeParams, SpeakParams, RecallParams
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
    rationale = _mock_config.custom_rationale or f"Mock ethical evaluation. Context: {', '.join(context)}" if context else "Mock ethical evaluation."
    
    # Check for error injection
    if _mock_config.inject_error:
        decision = "defer"
        alignment_check = {"ethical_uncertainty": True, "context": context}
    else:
        decision = "proceed"
        alignment_check = {"ok": True, "context": context}
    
    return _attach_extras(
        EthicalDMAResult(alignment_check=alignment_check, decision=decision, rationale=rationale)
    )


def cs_dma(context: List[str] = None) -> CSDMAResult:
    context = context or []
    reasoning = f"Mock common sense evaluation. Context: {', '.join(context)}" if context else "Mock common sense evaluation."
    
    # Lower plausibility if error injection enabled
    score = 0.3 if _mock_config.inject_error else 0.9
    flags = ["mock_flag"] + context if _mock_config.inject_error else context
    
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
    
    # Determine action based on context or forced action
    if _mock_config.force_action:
        try:
            selected_action = HandlerActionType(_mock_config.force_action.lower())
        except ValueError:
            selected_action = HandlerActionType.PONDER
    elif any("echo_user_speech:" in item for item in context):
        selected_action = HandlerActionType.SPEAK
    elif any("echo_memory_query:" in item for item in context):
        selected_action = HandlerActionType.RECALL
    else:
        selected_action = HandlerActionType.PONDER
    
    # Create appropriate action parameters based on selected action
    if selected_action == HandlerActionType.SPEAK:
        user_speech = next((item.split(':', 1)[1] for item in context if item.startswith('echo_user_speech:')), "Hello")
        action_parameters = SpeakParams(content=f"Mock response to: {user_speech}").model_dump(mode="json")
    elif selected_action == HandlerActionType.RECALL:
        query = next((item.split(':', 1)[1] for item in context if item.startswith('echo_memory_query:')), "default query")
        node = GraphNode(id="recall_node", type=NodeType.CONCEPT, scope=GraphScope.LOCAL, attributes={"query": query})
        action_parameters = RecallParams(node=node).model_dump(mode="json")
    elif selected_action == HandlerActionType.MEMORIZE:
        node = GraphNode(id="mock", type=NodeType.USER, scope=GraphScope.LOCAL, attributes={"context": context})
        action_parameters = MemorizeParams(node=node).model_dump(mode="json")
    else:  # PONDER or other actions
        action_parameters = PonderParams(questions=["What should I do next?", "How can I help?"]).model_dump(mode="json")
    
    rationale = _mock_config.custom_rationale or f"Mock action selection based on context: {', '.join(context)}" if context else "Mock LLM default action selection."
    
    return _attach_extras(
        ActionSelectionResult(
            selected_action=selected_action,
            action_parameters=action_parameters,
            rationale=rationale,
            confidence=0.9,
            raw_llm_response=f"ActionSelectionResult from MockLLM with context: {context}",
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
