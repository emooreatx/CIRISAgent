# Repository Guidelines for CIRISAgent Contributors

- RECENT REFACTOR! TESTS ARE BROKEN STILL!
- Always run `pytest -q` before committing changes.
- Prefer asynchronous functions when dealing with I/O or long-running tasks. Use `asyncio.to_thread` for blocking calls.
- Keep new scripts and services minimal and well-documented.


- After the setup script completes, the environment is locked down: only
  packages listed in `requirements.txt` are available and network access is
  disabled. Add new dependencies to that file and move on if you face issues testing

