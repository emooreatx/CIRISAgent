# Repository Guidelines for CIRISAgent Contributors

- RECENT REFACTOR! TESTS ARE BROKEN STILL!
- Always run `pytest -q` before committing changes.
- Prefer asynchronous functions when dealing with I/O or long-running tasks. Use `asyncio.to_thread` for blocking calls.
- Keep new scripts and services minimal and well-documented.
- All handler logic now lives under `ciris_engine/action_handlers`. The old
  `memory/` and `ponder/` packages were removed. When adding new handlers use the
  service registry via `BaseActionHandler.get_*_service()` for communication,
  memory, and other services. See `registries/README.md` for details on the
  registry and fallback behavior.

- Configure logging using `ciris_engine.utils.logging_config.setup_basic_logging`
  and access the application configuration with
  `ciris_engine.config.config_manager.get_config()`.

- After the setup script completes, the environment is locked down: only
  packages listed in `requirements.txt` are available and network access is
  disabled. Add new dependencies to that file and move on if you face issues testing

