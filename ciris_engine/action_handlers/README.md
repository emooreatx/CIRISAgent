# action_handlers

Collection of handlers that perform the actions selected by the DMAs.

Every handler derives from `BaseActionHandler` which exposes convenience
methods like `get_communication_service()` or `get_tool_service()`. These
methods look up providers in the service registry so the same handler works in
CLI, Discord and API runtimes without modification.
