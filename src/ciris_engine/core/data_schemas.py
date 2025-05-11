from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
import uuid
import collections # For the deque type hint later
from enum import Enum # Added for HandlerActionType

# --- Enums for Status Fields ---

class TaskStatus(BaseModel):
    status: Literal["pending", "active", "completed", "paused", "failed"] = "pending"

class ThoughtStatus(BaseModel):
    status: Literal["pending", "queued", "processing", "processed", "deferred", "failed", "cancelled"] = "pending"

class ThoughtType(BaseModel):
    type: Literal["thought", "metathought"] = "thought"

# --- Pydantic Models for Database Tables ---

class Task(BaseModel):
    """
    Represents a task in the tasks_table.
    These are broader objectives or operational directives for the agent.
    """
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = Field(..., description="A human-readable description of the task.")
    priority: int = Field(default=0, description="Priority of the task (e.g., 0-10, higher means more important).")
    status: TaskStatus = Field(default_factory=TaskStatus)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    due_date: Optional[datetime] = Field(default=None, description="Optional due date for the task.")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Any relevant context for the task (e.g., channel, user).")
    # Example: Could link to a project or a higher-level goal
    parent_goal_id: Optional[str] = Field(default=None)

    @model_validator(mode='before')
    def set_updated_at(cls, values):
        values['updated_at'] = datetime.utcnow()
        return values

    class Config:
        validate_assignment = True # Ensures updated_at is refreshed on modification

class Thought(BaseModel):
    """
    Represents a thought or metathought in the thoughts_table.
    These are discrete units of reasoning, information, or actions derived from tasks.
    """
    thought_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_task_id: str = Field(..., description="The ID of the task this thought originates from or relates to.")
    thought_type: ThoughtType = Field(default_factory=ThoughtType)
    content: Union[str, Dict[str, Any]] = Field(..., description="The actual content of the thought. Can be text or structured data.")
    priority: int = Field(default=0, description="Priority of the thought, can be inherited or adjusted from the task.")
    status: ThoughtStatus = Field(default_factory=ThoughtStatus)
    round_created: int = Field(..., description="The processing round number in which this thought was generated.")
    round_processed: Optional[int] = Field(default=None, description="The round number when this thought was last processed.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # For metathoughts, this could link to the thought it's about
    related_thought_id: Optional[str] = Field(default=None)
    # Context specific to the thought, can include DMA inputs/outputs if complex
    processing_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Context for processing, like DMA results or intermediate data.")
    # For tracking which DMA might handle it or its output
    dma_handler: Optional[Literal["CSDMA", "DSDMA", "PDMA", "None"]] = Field(default=None)
    # Store the result of processing this thought.
    processing_result: Optional[Dict[str, Any]] = Field(default=None, description="The outcome or result of processing this thought.")
    ponder_notes: Optional[List[str]] = Field(default=None, description="Key questions or notes if the thought was re-queued for pondering.")
    ponder_count: int = Field(default=0, description="Number of times this thought has been re-queued for pondering.")


    @model_validator(mode='before')
    def set_updated_at(cls, values):
        # This will run before other validators if an instance is created from a dict.
        # For updates, you might need to handle this in your update logic.
        if isinstance(values, dict):
            values['updated_at'] = datetime.utcnow()
        return values

    @model_validator(mode='after')
    def check_metathought_relation(cls, instance):
        if instance.thought_type.type == "metathought" and instance.related_thought_id is None:
            # This could be a warning or raise an error depending on strictness
            print(f"Warning: Metathought {instance.thought_id} has no related_thought_id.")
            # raise ValueError("Metathoughts must have a related_thought_id")
        return instance

    class Config:
        validate_assignment = True # Ensures updated_at is refreshed on modification (partially, see validator)


# --- Pydantic Model for Items in the In-Memory Thought Queue ---

class ThoughtQueueItem(BaseModel):
    """
    Represents an item loaded into the in-memory thought_queue (collections.deque) for a specific round.
    This is a subset of data from the Thought model, or a direct reference,
    optimized for what the DMAs need immediately.
    """
    thought_id: str
    source_task_id: str
    thought_type: ThoughtType # Using the Pydantic model here
    content: Union[str, Dict[str, Any]]
    priority: int
    # You might include the full thought_details from the original prompt if that's what gets queued
    # For example, the 'String' from the original prompt: "Lady_v said in #agent-test: ..."
    # This could be part of the 'content' field if it's structured, or a separate field.
    raw_input_string: Optional[str] = Field(default=None, description="The original input string that generated this thought, if applicable.")
    # Context from the `thought_in` structure
    initial_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Initial context when the thought was first received/generated.")
    ponder_notes: Optional[List[str]] = Field(default=None, description="Key questions from a previous Ponder action if re-queued.")


    # You can add a classmethod to easily convert a Thought db model to a ThoughtQueueItem
    @classmethod
    def from_thought_db(cls, thought_db_instance: Thought, raw_input: Optional[str] = None, initial_ctx: Optional[Dict[str, Any]] = None) -> "ThoughtQueueItem":
        return cls(
            thought_id=thought_db_instance.thought_id,
            source_task_id=thought_db_instance.source_task_id,
            thought_type=thought_db_instance.thought_type, # Pass the Pydantic model instance
            content=thought_db_instance.content,
            priority=thought_db_instance.priority,
            raw_input_string=raw_input if raw_input else str(thought_db_instance.content), # Fallback if raw_input not specifically passed
            initial_context=initial_ctx if initial_ctx else thought_db_instance.processing_context,
            ponder_notes=thought_db_instance.ponder_notes
        )

# --- Example: Type Hint for the Queue Itself ---
ThoughtQueue = collections.deque[ThoughtQueueItem]


class EntropyResult(BaseModel):
    entropy: float = Field(..., ge=0.0, le=1.0)
    # Optional: Add a field for LLM's brief reasoning if you want to prompt for it
    # reasoning: Optional[str] = None

class CoherenceResult(BaseModel):
    coherence: float = Field(..., ge=0.0, le=1.0)
    # reasoning: Optional[str] = None

class PrincipleEvaluation(BaseModel):
    evaluation: str = Field(..., description="Evaluation against this principle.")
    # You could add a score or other fields if needed later

class AlignmentCheckDetail(BaseModel):
    do_good: Optional[Union[str, PrincipleEvaluation]] = Field(default=None, description="Evaluation for Do-Good principle.")
    avoid_harm: Optional[Union[str, PrincipleEvaluation]] = Field(default=None, description="Evaluation for Avoid-Harm principle.")
    honor_autonomy: Optional[Union[str, PrincipleEvaluation]] = Field(default=None, description="Evaluation for Honor-Autonomy principle.")
    ensure_fairness: Optional[Union[str, PrincipleEvaluation]] = Field(default=None, description="Evaluation for Ensure-Fairness principle.")
    fidelity_transparency: Optional[Union[str, PrincipleEvaluation]] = Field(default=None, description="Evaluation for Fidelity/Transparency principle.")
    integrity: Optional[Union[str, PrincipleEvaluation]] = Field(default=None, description="Evaluation for Integrity principle.")
    meta_goal_m1: Optional[Union[str, PrincipleEvaluation]] = Field(default=None, description="Evaluation for Meta-Goal M-1 (adaptive coherence).")
    plausible_actions: Optional[List[str]] = Field(default_factory=list, description="Plausible actions considered.")
    # Make all fields optional with defaults for now to avoid cascading new "missing field" errors
    # if the LLM doesn't generate all of them. Once it generates the dict, we can make them required.

class EthicalPDMAResult(BaseModel):
    """
    Represents the structured output of the initial Ethical PDMA.
    The field names are designed to match the expected keys from the LLM response
    when using populate_by_name=True.
    """
    context_analysis: Union[str, Dict[str, Any]] = Field(..., alias="Context", description="Restatement of the user's request, affected stakeholders, and constraints.")
    alignment_check: AlignmentCheckDetail = Field(..., alias="Alignment-Check", description="Evaluation of plausible actions against ethical principles.") # CHANGED to use the new model
    conflicts: Optional[str] = Field(default=None, alias="Conflicts", description="Identified trade-offs or principle conflicts.")
    resolution: Optional[str] = Field(default=None, alias="Resolution", description="How conflicts were resolved based on ethical guidelines.") # Kept as Optional[str] as per latest file content before this change
    decision_rationale: str = Field(..., alias="Decision", description="The ethically-optimal action and its rationale.")
    monitoring_plan: Union[str, Dict[str, Any]] = Field(..., alias="Monitoring", description="Concrete metric and update plan for the decision.")
    raw_llm_response: Optional[str] = Field(default=None, description="The raw LLM response for auditing.")

    class Config:
        populate_by_name = True 
        validate_assignment = True


class CSDMAResult(BaseModel):
    """
    Represents the structured output of the Common Sense DMA.
    """
    common_sense_plausibility_score: float = Field(..., ge=0.0, le=1.0, description="Overall common sense plausibility (0.0 to 1.0, 1.0 = highly plausible).")
    flags: List[str] = Field(default_factory=list, description="List of flags indicating potential common sense violations (e.g., 'Physical_Implausibility', 'Atypical_Approach').")
    reasoning: str = Field(..., description="Brief explanation from the LLM for the score and flags.")
    raw_llm_response: Optional[str] = Field(default=None, description="The raw response from the LLM for debugging/auditing.")


class DSDMAResult(BaseModel):
    """
    Represents the structured output of a Domain-Specific DMA.
    """
    domain_name: str = Field(..., description="Name of the domain the DSDMA evaluated for (e.g., 'BasicTeacherMod').")
    domain_specific_score: float = Field(..., ge=0.0, le=1.0, description="Score reflecting alignment with domain-specific principles/goals (0.0 to 1.0).")
    recommended_action: Optional[str] = Field(default=None, description="A domain-specific action recommended by the DSDMA (e.g., 'Issue gentle reminder', 'Use specific emoji', 'No action').")
    flags: List[str] = Field(default_factory=list, description="List of flags indicating domain-specific considerations or violations.")
    reasoning: str = Field(..., description="Brief explanation from the DSDMA for its score, flags, and recommendation.")
    raw_llm_response: Optional[str] = Field(default=None, description="The raw response from the LLM for debugging/auditing, if an LLM was used.")


class HandlerActionType(str, Enum):
    SPEAK = "Speak"
    USE_TOOL = "Use Tool"
    LISTEN = "Listen"
    PONDER = "Ponder"
    REJECT_THOUGHT = "Reject Thought" # Explicit rejection of the input thought/request
    DEFER_TO_WA = "Defer to WA"
    NO_ACTION = "No Action" # If the synthesis decides no explicit action is best


class ActionSelectionPDMAResult(BaseModel):
    """
    Represents the structured output of the Action Selection PDMA.
    This PDMA synthesizes inputs from CSDMA, DSDMA, and an initial Ethical PDMA
    to choose a single handler action.
    """
    # The 6 PDMA steps, but focused on selecting a handler action
    context_summary_for_action_selection: str = Field(..., description="Restatement of the situation leading to action selection, considering all DMA inputs.")
    action_alignment_check: Dict[str, Any] = Field(..., description="Evaluation of plausible *handler actions* against ethical principles, informed by prior DMA outputs.")
    action_conflicts: Optional[Union[str, Dict[str, Any]]] = Field(default=None, description="Conflicts encountered when choosing between handler actions.") 
    action_resolution: Optional[Union[str, Dict[str, Any]]] = Field(default=None, description="How conflicts between potential handler actions were resolved.") # CHANGED from Optional[str]
    selected_handler_action: HandlerActionType = Field(..., description="The single, concrete handler action selected.")
    action_parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parameters for the selected action (e.g., message for Speak, tool_name for Use Tool).")
    action_selection_rationale: str = Field(..., description="The reasoning for selecting this specific handler action and its parameters, considering all DMA inputs.")
    monitoring_for_selected_action: Optional[Union[str, Dict[str, Any]]] = Field(default=None, description="Monitoring plan specifically for the chosen handler action.") # CHANGED
    raw_llm_response: Optional[str] = Field(default=None, description="The raw response from the LLM for debugging/auditing.")
    
    class Config: # Added Config for consistency, though not strictly needed for these changes yet
        validate_assignment = True


# --- Helper Functions for SQLite Table Creation (Illustrative) ---

def get_task_table_schema() -> str:
    return """
    CREATE TABLE IF NOT EXISTS tasks_table (
        task_id TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        priority INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        due_date TIMESTAMP,
        context_json TEXT,
        parent_goal_id TEXT
    );
    """

def get_thoughts_table_schema() -> str:
    return """
    CREATE TABLE IF NOT EXISTS thoughts_table (
        thought_id TEXT PRIMARY KEY,
        source_task_id TEXT NOT NULL,
        thought_type TEXT DEFAULT 'thought',
        content_json TEXT NOT NULL, -- Store structured content as JSON string
        priority INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        round_created INTEGER NOT NULL,
        round_processed INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        related_thought_id TEXT,
        processing_context_json TEXT,
        dma_handler TEXT,
        processing_result_json TEXT,
        ponder_notes_json TEXT, -- Added for ponder notes
        ponder_count INTEGER DEFAULT 0, -- Added for ponder count
        FOREIGN KEY (source_task_id) REFERENCES tasks_table(task_id)
            ON DELETE CASCADE,
        FOREIGN KEY (related_thought_id) REFERENCES thoughts_table(thought_id)
            ON DELETE SET NULL
    );
    """

# --- Example Usage (Conceptual) ---
if __name__ == "__main__":
    # Example Task
    task1_data = {
        "description": "Respond to user queries in #agent-test channel.",
        "priority": 5,
        "context": {"channel": "agent-test"}
    }
    task1 = Task(**task1_data)
    print("--- Task Example ---")
    print(task1.model_dump_json(indent=2))

    # Example Thought
    thought1_data = {
        "source_task_id": task1.task_id,
        "thought_type": {"type": "thought"}, # Pass as dict to ThoughtType
        "content": {"user_query": "Tell me about murres.", "original_message_id": "msg123"},
        "priority": task1.priority,
        "round_created": 1,
        "processing_context": { # This could be the `thought_in` from your example
            "id": "thought-abcde",
            "Top Tasks": ["Moderation request 05763434"],
            "environment_context": { # Renamed from 'context' to avoid Pydantic field name clash
                "environment": "discord",
                "channel": "agent-test",
                "agent_name": "CIRIS Covenant Bot"
            }
        }
    }
    thought1 = Thought(**thought1_data)
    print("\n--- Thought Example ---")
    print(thought1.model_dump_json(indent=2))

    # Update a thought (demonstrates updated_at, though manual for this example)
    # In a real app, you'd fetch, modify, then save, and the ORM/save logic would handle updated_at
    thought1.status = ThoughtStatus(status="queued")
    thought1.updated_at = datetime.utcnow() # Manually setting for demo; model_validator helps on creation
    print("\n--- Updated Thought Example ---")
    print(thought1.model_dump_json(indent=2))


    # Example ThoughtQueueItem from the thought
    queue_item1 = ThoughtQueueItem.from_thought_db(thought1, raw_input="User asked: Tell me about murres.")
    print("\n--- ThoughtQueueItem Example ---")
    print(queue_item1.model_dump_json(indent=2))

    # Initialize the queue
    current_round_queue: ThoughtQueue = collections.deque()
    current_round_queue.append(queue_item1)

    print(f"\nQueue has {len(current_round_queue)} item(s).")

    # Example processing
    if current_round_queue:
        item_to_process = current_round_queue.popleft()
        print(f"\nProcessing from queue: {item_to_process.thought_id}")
        # ... pass item_to_process.content and other fields to DMA ...
        # Update status in the main thoughts_table (SQLite)
        # thought1_db.status = "processing"
        # thought1_db.save_to_db()

    print("\n--- SQLite Schemas ---")
    print("Task Table Schema:")
    print(get_task_table_schema())
    print("\nThoughts Table Schema:")
    print(get_thoughts_table_schema())
