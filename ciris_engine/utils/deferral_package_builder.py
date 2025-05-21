from ciris_engine.utils.context_formatters import format_system_snapshot_for_prompt, format_user_profiles_for_prompt
from ciris_engine.utils.task_formatters import format_task_context

def build_deferral_package(thought, parent_task, ethical_pdma_result=None, csdma_result=None, dsdma_result=None, trigger_reason=None, extra=None):
    """
    Build a rich deferral package for DEFER actions, including all relevant context and DMA results.
    """
    package = {
        "thought_id": getattr(thought, 'thought_id', None),
        "thought_content": getattr(thought, 'content', None),
        "parent_task_id": getattr(thought, 'source_task_id', None),
        "parent_task_description": getattr(parent_task, 'description', None) if parent_task else None,
        "trigger": trigger_reason,
        "ethical_pdma_result": ethical_pdma_result.model_dump() if ethical_pdma_result and hasattr(ethical_pdma_result, 'model_dump') else str(ethical_pdma_result),
        "csdma_result": csdma_result.model_dump() if csdma_result and hasattr(csdma_result, 'model_dump') else str(csdma_result),
        "dsdma_result": dsdma_result.model_dump() if dsdma_result and hasattr(dsdma_result, 'model_dump') else str(dsdma_result),
        "user_profiles": None,
        "system_snapshot": None,
        "formatted_user_profiles": None,
        "formatted_system_snapshot": None,
        "formatted_task_context": None,
    }
    # Add user profiles and system snapshot if present
    processing_context = getattr(thought, 'processing_context', {}) or {}
    system_snapshot = processing_context.get('system_snapshot')
    user_profiles = None
    if system_snapshot:
        user_profiles = system_snapshot.get('user_profiles')
        package["user_profiles"] = user_profiles
        package["system_snapshot"] = system_snapshot
        package["formatted_user_profiles"] = format_user_profiles_for_prompt(user_profiles)
        package["formatted_system_snapshot"] = format_system_snapshot_for_prompt(system_snapshot, processing_context)
    # Add formatted task context
    if parent_task:
        recent_actions = getattr(parent_task, 'recent_actions', [])
        completed_tasks = getattr(parent_task, 'completed_tasks', None)
        # Always get the channel from the parent_task if present
        package["channel_id"] = getattr(parent_task, 'channel_id', None)
        # Robustly handle MagicMock or non-dict parent_task in tests
        task_dict = None
        if hasattr(parent_task, 'model_dump'):
            maybe_dict = parent_task.model_dump()
            if isinstance(maybe_dict, dict):
                task_dict = maybe_dict
        if task_dict is None:
            try:
                maybe_dict = dict(parent_task)
                if isinstance(maybe_dict, dict):
                    task_dict = maybe_dict
            except Exception:
                pass
        # If still not a dict (e.g., MagicMock), use a minimal fallback
        if not isinstance(task_dict, dict):
            # Try to extract minimal fields for test robustness
            task_dict = {
                "description": getattr(parent_task, "description", "[mocked task]"),
                "task_id": getattr(parent_task, "task_id", "mocked-task-id"),
                "status": getattr(parent_task, "status", "N/A"),
                "priority": getattr(parent_task, "priority", "N/A"),
            }
        package["formatted_task_context"] = format_task_context(task_dict, recent_actions, completed_tasks)
    if extra:
        package.update(extra)
    return package
