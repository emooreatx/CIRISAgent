# Repository Guidelines for CIRISAgent Contributors

- Always run `pytest -q` before committing changes.
- Prefer asynchronous functions when dealing with I/O or long-running tasks. Use `asyncio.to_thread` for blocking calls.
- Keep new scripts and services minimal and well-documented.

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
| graceful_shutdown      | Yes       | 10s max shutdown per service                                 |

### Runtime Architecture

`BaseRuntime` centralizes environment validation, audit logging, and the Dream Protocol. IO adapters expose a small interface (`fetch_inputs` and `send_output`) so new platforms can be added easily. Incoming Discord messages are deduplicated: each message ID maps to exactly one Task and one initial Thought. The helper `_create_task_if_new` performs this check before persisting.
