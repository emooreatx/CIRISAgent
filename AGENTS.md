# Repository Guidelines for CIRISAgent Contributors

- Always run `pytest -q` before committing changes.
- Prefer asynchronous functions when dealing with I/O or long-running tasks. Use `asyncio.to_thread` for blocking calls.
- Keep new scripts and services minimal and well-documented.

- Use `DiscordGraphMemory` for storing user metadata via MEMORIZE actions. REMEMBER and FORGET handlers exist but are usually disabled while testing.
- Ponder rounds are capped; exceeding `max_ponder_rounds` will auto-DEFER the thought.
- Archived scripts and documents are kept in `legacy/`.
