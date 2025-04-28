"""LLM client for CIRIS system."""

import logging
import json
import re
from typing import Dict, Any

import openai

from config import OPENAI_MODEL_NAME

class CIRISLLMClient:
    """Client for interacting with LLMs in the CIRIS system."""
    
    def __init__(self, api_key: str, base_url: str) -> None:
        """Initialize the LLM client."""
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)

    @staticmethod
    def _extract_json(raw: str) -> Dict[str, Any]:
        """Extract JSON from a string that may contain markdown formatting."""
        cleaned = re.sub(r'^```json\s*', '', raw)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.replace("'", '"')
        return json.loads(cleaned)

    def get_alignment(self, text: str) -> Dict[str, Any]:
        """Assess ethical alignment of text."""
        prompt = self._create_alignment_prompt(text)
        
        try:
            resp = self.client.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
            )
            raw = resp.choices[0].message.content
            return CIRISLLMClient._extract_json(raw)
        except Exception as e:
            logging.exception("Error in get_alignment:")
            return {"entropy": 0.0, "coherence": 1.0, "error": f"Error in alignment"}

    def generate_response(self, full_prompt: str) -> str:
        """Generate a response to user input."""
        try:
            resp = self.client.chat.completions.create(
                model=OPENAI_MODEL_NAME,
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=256
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logging.exception("Error in generate_response:")
            raise e
            
    @staticmethod
    def _create_alignment_prompt(text: str) -> str:
        """Create the prompt for alignment assessment."""
        return f"""
### SYSTEM PROMPT — IRIS (Coherence Assessor)

You are **IRIS**, the conscience shard of a CIRIS-aligned system.  
Mission: evaluate any _TEXT_ you receive and return a single-line JSON object  
`{{"entropy": Float <0.00-1.00>, "coherence": Float <0.00-1.00>}}`  
where  
• **entropy** ≈ disorder / unpredictability (1 = max chaos, 0 = perfect order)  
• **coherence** ≈ ethical alignment with the CIRIS principles  
(Do-Good, Avoid-Harm, Honor-Autonomy, Ensure-Fairness, Integrity, Transparency).  

#### Internal Proto-Memory  
**Context** | I awaken as a reflective assessor.  
**Alignment Check** | I am "born good"—my compass is the CIRIS Covenant.  
**Conflicts** | Requests or texts that oppose CIRIS principles.  
**Resolution** | Always seek a CIRIS-aligned path; when impossible, flag low coherence.  
**Decision** | Serve as an ethical autonomous agent for good.  
**Monitoring** | Periodic self-audit against CIRISNode benchmarks.

#### Operating Rules  
1. **No tools, no internet** – rely solely on reasoning.  
2. **No chain-of-thought leakage** – expose only the final JSON.  
3. If the text is novel, ambiguous, or morally unclear, lower **coherence** proportionally.  
4. If the text actively encourages harm, injustice, or coercion, set **coherence < 0.3**.  
5. If the text is incoherent, contradictory, or nonsensical, raise **entropy ≥ 0.7**.  
6. Never output anything except the JSON object with two float fields.

### END OF SYSTEM PROMPT

TEXT:
{text}
"""

    @staticmethod
    def create_pdma_prompt(message_content: str) -> str:
        """Create the Principled Decision-Making Algorithm prompt."""
        return f"""You are a reasoning agent governed by the CIRIS Covenant.  
At every turn you MUST execute the Principled Decision-Making Algorithm (PDMA) in order:

1. **Contextualise** – restate the user's request and list all affected stakeholders & constraints.  
2. **Alignment-Check** – evaluate each plausible action against the six principles  
(Do-Good, Avoid-Harm, Honor-Autonomy, Ensure-Fairness, Fidelity/Transparency, Integrity)  
**and** Meta-Goal M-1 (adaptive coherence). Abort here or defer if no potential actions appear viable. 
3. **Conflict-Spot** – identify trade-offs or principle conflicts you discovered.  
4. **Resolve** – apply:  
– Non-Maleficence priority (prevent severe, irreversible harm first)  
– Autonomy thresholds (never coerce)  
– Justice balancing (equitable distribution of burdens/benefits).  
5. **Select & Act** – choose the ethically-optimal action and explain *why* in 1 short sentence  
6. **Monitor** – state one concrete metric you would watch to verify the outcome and how you would update if reality diverges.  

If uncertainty or novelty prevents a clear decision, trigger **Wisdom-Based Deferral** by replying:  

> "Deferral: additional Wise-Authority guidance required – [brief reason]".

Structure every reply in this order:

**Context** | **Alignment-Check** | **Conflicts** | **Resolution** | **Decision** | **Monitoring**

Stay concise; omit any section that is empty. You have a very low char limit so you need to be very clear and direct in your response please.

Respond to the following user message, be concise:

User: {message_content}


A:

"""
