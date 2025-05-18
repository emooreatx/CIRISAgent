# Repository Guidelines for CIRISAgent Contributors

- Always run `pytest -q` before committing changes.
- Prefer asynchronous functions when dealing with I/O or long-running tasks. Use `asyncio.to_thread` for blocking calls.
- Keep new scripts and services minimal and well-documented.

- Use `DiscordGraphMemory` for storing user metadata; avoid writing to the graph elsewhere.
- Archived scripts and documents are kept in `legacy/`.
