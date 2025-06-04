# Repository Guidelines for CIRISAgent Contributors

- All unit tests are currently passing. Ensure they remain green by running
  `pytest -q` before committing changes.
- Prefer asynchronous functions when dealing with I/O or long-running tasks. Use `asyncio.to_thread` for blocking calls.
- Keep new scripts and services minimal and well-documented.
- All handler logic now lives under `ciris_engine/action_handlers`. The old
  `memory/` and `ponder/` packages were removed. When adding new handlers use the
  service registry via `BaseActionHandler.get_*_service()` for communication,
  memory, and other services. See `registries/README.md` for details on the
  registry and fallback behavior.
- Ensure `OPENAI_API_KEY` is set (or a local equivalent) before running tests.

- Action handlers must follow the standard BaseActionHandler pattern. Each handler defines `action_type` and implements `handle(thought, params, dispatch_context) -> bool`.
- Replace any direct service usage (e.g. discord_service.send_message) with registry lookups like `get_communication_service()`.

- Validate handler parameters using Pydantic models. If `params` is a dict, cast it to the proper `*Params` model before using it.
- Do not compare action names with string literals. Use the `HandlerActionType` enums instead.

- Configure logging using `ciris_engine.utils.logging_config.setup_basic_logging`
  and access the application configuration with
  `ciris_engine.config.config_manager.get_config()`.

- After the setup script completes, the environment is locked down: only
  packages listed in `requirements.txt` are available and network access is
  disabled. Add new dependencies to that file and move on if you face issues testing

- Each submodule under `ciris_engine/` should include a brief `README.md`
  describing its purpose and how to use it. Add one if it doesn't exist when
  modifying a module.

- Use `python main.py --help` to see the unified runtime options. The same flags
  map directly to runtime arguments (e.g., `--host`, `--port`, `--no-interactive`).
  For offline tests pass `--mock-llm` to run without network access.
- The ongoing refactor is tracked in `ECHO_Refactor.md`. Begin or continue the
  lowest numbered incomplete task in that file and update its status when you
  work on it.

- Follow the ECHO refactor tasks aggressively: delete outdated code and tests rather than adapting them. Each commit should clearly reference the task being advanced.
