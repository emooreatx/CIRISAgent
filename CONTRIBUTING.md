# Contributing to CIRIS Engine

Thank you for your interest in contributing to the CIRIS Engine project!

## Development Guidelines

### Task and Thought Creation

When integrating new input sources or agents, please adhere to the following conventions for creating Tasks and Thoughts:

-   **Always store raw external input in `Task.context` under the key `"initial_input_content"`.**
    For example, when a new Discord message is received, the `Task` object created should have its `context` dictionary populated like this:
    ```python
    task_context = {
        "initial_input_content": message.content, # The raw Discord message
        "environment": "discord_bot_xyz",
        # ... other relevant metadata ...
    }
    new_task = Task(..., context=task_context)
    ```
    The `ThoughtQueueManager` uses `Task.context["initial_input_content"]` (or falls back to `Task.description`) to populate the content of the initial "seed thought".

-   **The engine auto-generates a "seed thought"; do not add initial `Thought`s manually for new tasks.**
    When a new `Task` is added via `ThoughtQueueManager.add_task()`, the `ThoughtQueueManager.populate_round_queue()` method will automatically detect this new task (if it's "active" and has no pending/processing thoughts) and generate an initial "seed\_task\_thought" for it. Your agent code should only be responsible for creating and adding the `Task`.

Adhering to these guidelines ensures consistency in how new work enters the CIRIS Engine processing pipeline.

### Agent Profiles

The CIRIS Engine uses agent profiles to define the "personality" and specific configurations for different agent behaviors. This includes specifying the Domain-Specific Decision-Making Algorithm (DSDMA) and any overrides for action selection prompts.

**Creating a New Profile:**

1.  **Define your DSDMA Class:**
    *   Create a new Python class that inherits from `ciris_engine.dma.dsdma_base.BaseDSDMA`.
    *   Implement the `evaluate_thought` method and define a `DOMAIN_NAME` and a `DEFAULT_TEMPLATE` for its system prompt.
    *   Ensure your DSDMA class's `__init__` method calls `super().__init__(...)` and accepts `aclient` (the instructor-patched OpenAI client) and `model_name`, plus any `domain_specific_knowledge` or `prompt_template` overrides it might need from `dsdma_kwargs`.
    *   Place this class in a suitable location, e.g., `src/ciris_engine/dma/dsdma_yournewprofile.py`.
    *   Export your new DSDMA class from `src/ciris_engine/dma/__init__.py`.

2.  **Create a Profile YAML File:**
    *   Create a new YAML file in the `ciris_profiles/` directory (e.g., `ciris_profiles/yournewprofile.yaml`).
    *   The YAML file should have the following structure:
        ```yaml
        name: YourProfileName # e.g., "Researcher", "HelperBot"
        dsdma_cls: ciris_engine.dma.YourNewDSDMAClassName # Full Python path to your DSDMA class
        dsdma_kwargs: # Optional: Arguments to pass to your DSDMA's __init__
          some_custom_knowledge: "value"
          # prompt_template: | # You can override the DSDMA's DEFAULT_TEMPLATE here
          #   Your custom prompt template for this DSDMA instance...
        action_prompt_overrides: # Optional: Overrides for ActionSelectionPDMA prompts
          system_header: |
            You are acting for the YourProfileName agent. Prioritize X and Y.
          decision_format: | # Example override
            Return JSON with keys: action, confidence, rationale, and custom_field.
          # closing_reminder: |
          #   Remember to be Z.
        ```

**Using a Profile:**

1.  **Loading the Profile:**
    *   The `ciris_engine.utils.profile_loader.load_profile(path_to_yaml_file)` function is used to load profiles.
    *   Agent entry points (like `src/main_engine.py`, `src/agents/discord_agent/ciris_discord_bot_alpha.py`, `src/agents/cli_benchmark_agent.py`) are responsible for loading the desired profile.

2.  **Instantiating Components:**
    *   The loaded `AgentProfile` object provides:
        *   `profile.name`: The agent's name.
        *   `profile.dsdma_cls`: The DSDMA class to instantiate.
        *   `profile.dsdma_kwargs`: Keyword arguments for the DSDMA's constructor.
        *   `profile.action_prompt_overrides`: Overrides for the `ActionSelectionPDMAEvaluator`.
    *   These are used during the setup of the `WorkflowCoordinator` and its associated evaluators. Refer to `src/main_engine.py` or the Discord bot scripts for examples of how these are used.

By following this structure, you can easily define and integrate new agent personalities into the CIRIS Engine.
