from dataclasses import dataclass
from typing import Type, Dict, Any, Optional

from ciris_engine.dma.dsdma_base import BaseDSDMA # Corrected import

@dataclass
class AgentProfile:
    name: str                                  # "Teacher", "Student", "Moderator"…
    dsdma_cls: Type["BaseDSDMA"]               # Which DSDMA subclass to use
    dsdma_kwargs: Dict[str, Any] = None        # Inject custom domain knowledge / rules
    action_prompt_overrides: Optional[Dict[str, str]] = None
    # keys you allow:  "system_header", "decision_format", "closing_reminder" …
