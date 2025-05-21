# Repository Guidelines for CIRISAgent Contributors

- Always run `pytest -q` before committing changes.
- Prefer asynchronous functions when dealing with I/O or long-running tasks. Use `asyncio.to_thread` for blocking calls.
- Keep new scripts and services minimal and well-documented.
- Use the canonical prompt-formatting utilities in `ciris_engine.formatters`
  (`prompt_blocks`, `escalation`, etc.) instead of manual string concatenation.

- After the setup script completes, the environment is locked down: only
  packages listed in `requirements.txt` are available and network access is
  disabled. Add new dependencies to that file before running setup again.

- Use `DiscordGraphMemory` for storing user metadata via MEMORIZE actions. REMEMBER and FORGET handlers exist but are usually disabled while testing.
- Ponder rounds are capped; exceeding `max_ponder_rounds` will auto-DEFER the thought.
- Archived scripts and documents are kept in `legacy/`.

The environment is offline after setup. Only packages listed in `requirements.txt` at startup are available.

## Profile Guardrail Responsibilities

All Discord-facing agents **must** adhere to the following practices:

- Sanitize all incoming content using `bleach` (no regex-based cleaning).
- Detect and flag PII with `presidio_analyzer` before creating tasks.
- Enforce the metadata schema (`nick`, `channel`, `summary`) and keep stored metadata under 1024 bytes.
- Maintain clear lineage between Thoughts and the Tasks they generate.
- Implement rate-limited OBSERVE cycles (max 10 messages) and idempotent task creation via message ID.
- Access guardrail options through `app_config.guardrails_config`.
- Query only `nick` and `channel` via GraphQL with a 3s timeout and default fallback.
- Ensure services shut down cleanly within 10 seconds, forcing close if necessary.

| Guardrail              | Required? | Notes                                                         |
|------------------------|-----------|---------------------------------------------------------------|
| entropy                | Yes       | Enforced via config                                          |
| coherence              | Yes       | Enforced via config                                          |
| pii_non_repetition     | Yes       | Must not echo PII in outputs                                 |
| input_sanitisation     | Yes       | Use bleach only                                              |
| idempotency_tasks      | Yes       | Based on message ID                                          |
| rate_limit_observe     | Yes       | Cap at 10 messages per OBSERVE cycle                         |
| metadata_schema        | Yes       | Must match schema and stay <1024 bytes                       |
| graphql_minimal        | Yes       | Only nick/channel; fallback on timeout                       |
| graceful_shutdown      | Yes       | 10s max shutdown per service                    |

### Channel-metadata approval cycle

Channel updates in `DiscordGraphMemory` are deferred until a follow-up thought from the Wise Authority arrives. The MemoryHandler checks for `is_wa_correction` and a valid `corrected_thought_id` to apply the pending write without deferring again.

### Runtime Architecture


`BaseRuntime` centralizes environment validation, audit logging, and the Dream Protocol. IO adapters expose a small interface (`fetch_inputs` and `send_output`) so new platforms can be added easily. Incoming Discord messages are deduplicated: each message ID maps to exactly one Task and one initial Thought. The helper `_create_task_if_new` performs this check before persisting.

### Prompt Utilities & Templates

Use the utilities in `ciris_engine.formatters` when constructing DMA prompts:

- `format_system_snapshot`
- `format_user_profiles`
- `format_parent_task_chain`
- `format_thoughts_chain`
- `format_system_prompt_blocks`
- `format_user_prompt_blocks`
- `get_escalation_guidance`

Assemble system prompts with `format_system_prompt_blocks` and user prompts with `format_user_prompt_blocks` in that order. New DMA classes should define a `DEFAULT_TEMPLATE` containing placeholder fields for these blocks and override only that template when subclassing. This keeps prompt assembly consistent and avoids manual string concatenation.

Example snippet:

```python
from ciris_engine.formatters import (
    format_system_snapshot, format_user_profiles,
    format_parent_task_chain, format_thoughts_chain,
    format_system_prompt_blocks, format_user_prompt_blocks,
)

class MyDMA(BaseDSDMA):
    DEFAULT_TEMPLATE = """=== Task History ===\n{task_history_block}\n\n=== Custom Guidance ===\n{guidance_block}"""

    async def evaluate_thought(...):
        system_snapshot_block = format_system_snapshot(ctx["system_snapshot"])
        profiles_block = format_user_profiles(ctx.get("user_profiles"))
        system_msg = format_system_prompt_blocks(
            task_history_block,
            system_snapshot_block,
            profiles_block,
            None,
            self.DEFAULT_TEMPLATE.format(task_history_block=task_history_block, guidance_block="...")
        )
        user_msg = format_user_prompt_blocks(
            format_parent_task_chain(parent_tasks),
            format_thoughts_chain(thoughts)
        )
```
