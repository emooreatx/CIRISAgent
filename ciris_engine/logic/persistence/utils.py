import json
from typing import Any
from ciris_engine.schemas.runtime.models import Task, Thought, ThoughtContext, TaskContext, TaskOutcome, FinalAction
from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus
import logging
import uuid

logger = logging.getLogger(__name__)

def map_row_to_task(row: Any) -> Task:
    row_dict = dict(row)
    if row_dict.get("context_json"):
        try:
            ctx_data = json.loads(row_dict["context_json"])
            if isinstance(ctx_data, dict):
                # Don't set default system_snapshot - let the model validation handle the data as-is
                row_dict["context"] = TaskContext.model_validate(ctx_data)
            else:
                # Provide required fields for TaskContext
                row_dict["context"] = TaskContext(
                    channel_id=None,
                    user_id=None,
                    correlation_id=str(uuid.uuid4()),
                    parent_task_id=None
                )
        except Exception as e:
            logger.warning(f"Failed to decode context_json for task {row_dict.get('task_id')}: {e}")
            row_dict["context"] = TaskContext(
                channel_id=None,
                user_id=None,
                correlation_id=str(uuid.uuid4()),
                parent_task_id=None
            )
    else:
        row_dict["context"] = TaskContext(
            channel_id=None,
            user_id=None,
            correlation_id=str(uuid.uuid4()),
            parent_task_id=None
        )
    if row_dict.get("outcome_json"):
        try:
            outcome_data = json.loads(row_dict["outcome_json"])
            # Only set outcome if it's a non-empty dict with required fields
            if isinstance(outcome_data, dict) and outcome_data:
                row_dict["outcome"] = TaskOutcome.model_validate(outcome_data)
            else:
                row_dict["outcome"] = None
        except Exception:
            logger.warning(f"Failed to decode outcome_json for task {row_dict.get('task_id')}")
            row_dict["outcome"] = None
    else:
        row_dict["outcome"] = None

    # Remove database-specific columns that aren't in the Task schema
    for k in ["context_json", "outcome_json", "retry_count"]:
        if k in row_dict:
            del row_dict[k]

    try:
        row_dict["status"] = TaskStatus(row_dict["status"])
    except Exception:
        logger.warning(f"Invalid status value '{row_dict['status']}' for task {row_dict.get('task_id')}. Defaulting to PENDING.")
        row_dict["status"] = TaskStatus.PENDING
    return Task(**row_dict)

def map_row_to_thought(row: Any) -> Thought:
    row_dict = dict(row)
    if row_dict.get("context_json"):
        try:
            ctx_data = json.loads(row_dict["context_json"])
            if isinstance(ctx_data, dict) and ctx_data:  # Check if dict is not empty
                # Don't set default system_snapshot - let the model validation handle the data as-is
                row_dict["context"] = ThoughtContext.model_validate(ctx_data)
            else:
                # For empty or invalid context, set to None instead of trying to create invalid ThoughtContext
                row_dict["context"] = None
        except Exception as e:
            logger.warning(f"Failed to decode context_json for thought {row_dict.get('thought_id')}: {e}")
            # For failed decoding, set to None instead of trying to create invalid ThoughtContext
            row_dict["context"] = None
    else:
        # No context provided, set to None
        row_dict["context"] = None
    if row_dict.get("ponder_notes_json"):
        try:
            row_dict["ponder_notes"] = json.loads(row_dict["ponder_notes_json"])
        except Exception:
            logger.warning(f"Failed to decode ponder_notes_json for thought {row_dict.get('thought_id')}")
            row_dict["ponder_notes"] = None
    else:
        row_dict["ponder_notes"] = None
    if row_dict.get("final_action_json"):
        try:
            action_data = json.loads(row_dict["final_action_json"])
            # Only set final_action if it's a non-empty dict with required fields
            if isinstance(action_data, dict) and action_data:
                row_dict["final_action"] = FinalAction.model_validate(action_data)
            else:
                row_dict["final_action"] = None
        except Exception:
            logger.warning(f"Failed to decode final_action_json for thought {row_dict.get('thought_id')}")
            row_dict["final_action"] = None
    else:
        row_dict["final_action"] = None
    for k in ["context_json", "ponder_notes_json", "final_action_json"]:
        if k in row_dict:
            del row_dict[k]
    try:
        row_dict["status"] = ThoughtStatus(row_dict["status"])
    except Exception:
        logger.warning(f"Invalid status value '{row_dict['status']}' for thought {row_dict.get('thought_id')}. Defaulting to PENDING.")
        row_dict["status"] = ThoughtStatus.PENDING
    return Thought(**row_dict)
