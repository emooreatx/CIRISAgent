# Repository Guidelines for CIRISAgent Contributors

- Always run `pytest -q` before committing changes.
- Prefer asynchronous functions when dealing with I/O or long-running tasks. Use `asyncio.to_thread` for blocking calls.
- Keep new scripts and services minimal and well-documented.

- Use `DiscordGraphMemory` for storing user metadata via MEMORIZE actions. REMEMBER and FORGET handlers exist but are usually disabled while testing.
- Ponder rounds are capped; exceeding `max_ponder_rounds` will auto-DEFER the thought.
- Archived scripts and documents are kept in `legacy/`.

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
