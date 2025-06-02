# runtime

Implementations for running the agent in different environments.

- **CIRISRuntime** – base class that initializes the service registry and all
  core services.
- **DiscordRuntime** – registers Discord adapters with `Priority.HIGH` and also
  adds CLI services with `Priority.NORMAL` as a fallback.
- **CLIRuntime** – local runtime that registers only CLI based services.
- **APIRuntime** – exposes the agent via an HTTP API and registers the API
  adapter with high priority.

Each runtime waits for the service registry to become ready before processing
any thoughts. The registry checks that core services like communication,
memory, LLM, and audit logging are registered. The default timeout is 30
seconds, after which an error is logged and processing continues with whatever
services are available.
