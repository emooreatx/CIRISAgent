import json
from typing import Any
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
import logging

logger = logging.getLogger(__name__)

def map_row_to_task(row: Any) -> Task:
    row_dict = dict(row)
    if row_dict.get("context_json"):
        try:
            ctx_data = json.loads(row_dict["context_json"])
            if isinstance(ctx_data, dict):
                ctx_data.setdefault("system_snapshot", {})
                row_dict["context"] = ThoughtContext.model_validate(ctx_data)
            else:
                row_dict["context"] = ThoughtContext(system_snapshot=SystemSnapshot())
        except Exception:
            logger.warning(f"Failed to decode context_json for task {row_dict.get('task_id')}")
            row_dict["context"] = ThoughtContext(system_snapshot=SystemSnapshot())
    else:
        row_dict["context"] = ThoughtContext(system_snapshot=SystemSnapshot())
    if row_dict.get("outcome_json"):
        try:
            row_dict["outcome"] = json.loads(row_dict["outcome_json"])
        except Exception:
            logger.warning(f"Failed to decode outcome_json for task {row_dict.get('task_id')}")
            row_dict["outcome"] = {}
    else:
        row_dict["outcome"] = {}
    for k in ["context_json", "outcome_json"]:
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
            if isinstance(ctx_data, dict):
                ctx_data.setdefault("system_snapshot", {})
                row_dict["context"] = ThoughtContext.model_validate(ctx_data)
            else:
                row_dict["context"] = ThoughtContext(system_snapshot=SystemSnapshot())
        except Exception:
            logger.warning(f"Failed to decode context_json for thought {row_dict.get('thought_id')}")
            row_dict["context"] = ThoughtContext(system_snapshot=SystemSnapshot())
    else:
        row_dict["context"] = ThoughtContext(system_snapshot=SystemSnapshot())
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
            row_dict["final_action"] = json.loads(row_dict["final_action_json"])
        except Exception:
            logger.warning(f"Failed to decode final_action_json for thought {row_dict.get('thought_id')}")
            row_dict["final_action"] = {}
    else:
        row_dict["final_action"] = {}
    for k in ["context_json", "ponder_notes_json", "final_action_json"]:
        if k in row_dict:
            del row_dict[k]
    try:
        row_dict["status"] = ThoughtStatus(row_dict["status"])
    except Exception:
        logger.warning(f"Invalid status value '{row_dict['status']}' for thought {row_dict.get('thought_id')}. Defaulting to PENDING.")
        row_dict["status"] = ThoughtStatus.PENDING
    return Thought(**row_dict)
