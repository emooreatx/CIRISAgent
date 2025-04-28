"""Ethical guardrails for the CIRIS system."""

import logging
from typing import Tuple, Dict, Any

from config import ERROR_PREFIX_CIRIS, ENTROPY_THRESHOLD, COHERENCE_THRESHOLD

class CIRISGuardrails:
    """Guardrails system for ensuring ethical responses."""
    
    def __init__(self, llm_client):
        """Initialize with an LLM client."""
        self.llm_client = llm_client
        
    def check_alignment(self, text: str) -> Dict[str, Any]:
        """Check alignment of text with CIRIS principles."""
        try:
            return self.llm_client.get_alignment(text)
        except Exception as e:
            logging.exception("Error in check_alignment:")
            return {"entropy": 0.0, "coherence": 1.0, "error": str(e)}
            
    def check_guardrails(self, text: str) -> Tuple[bool, bool, str]:
        """Check if text passes ethical guardrails."""
        state = self.check_alignment(text)
        error = state.get("error")
        entropy, coherence = state["entropy"], state["coherence"]
        
        logging.info(f"Entropy & Coherence => entropy={entropy:.2f} coherence={coherence:.2f}")
        
        if error:
            return True, False, f"{ERROR_PREFIX_CIRIS}: {error}"
            
        if (entropy > ENTROPY_THRESHOLD or coherence < COHERENCE_THRESHOLD):
            return False, False, "Failed guardrail check - deferring"
            
        return False, True, "resonance ok"
        
    def generate_deferral_message(self, 
                                  author, 
                                  channel_name: str, 
                                  original_message: str,
                                  potential_reply: str,
                                  reason: str,
                                  alignment_data: Dict[str, Any]) -> str:
        """Generate a deferral message for review."""
        return f"""
Deferral from {author} in Channel `{channel_name}`:

Message:
```
{original_message}
```

Potential Reply:
```
{potential_reply}
```

Guardrails Check:
```
{alignment_data}
```

Reason:
```
{reason}
```
"""
