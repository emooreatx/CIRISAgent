# Contributing to CIRIS Engine

First off, thank you for considering contributing to CIRISEngine! Your help is appreciated.

This document provides guidelines for contributing to the project. Please read it before you start.

## Code of Conduct

This project and everyone participating in it is governed by a [Code of Conduct](CODE_OF_CONDUCT.md) (to be created). By participating, you are expected to uphold this code. Please report unacceptable behavior.

## How Can I Contribute?

There are many ways to contribute, from writing tutorials or blog posts, improving the documentation, submitting bug reports and feature requests or writing code which can be incorporated into CIRISEngine itself.

### Reporting Bugs

-   **Ensure the bug was not already reported** by searching on GitHub under [Issues](https://github.com/your-username/CIRISEngine/issues). (Replace `your-username/CIRISEngine` with the actual repository URL).
-   If you're unable to find an open issue addressing the problem, [open a new one](https://github.com/your-username/CIRISEngine/issues/new). Be sure to include a **title and clear description**, as much relevant information as possible, and a **code sample or an executable test case** demonstrating the expected behavior that is not occurring.
-   For bonus points, provide a **failing test** as a pull request.

### Suggesting Enhancements

-   Open a new issue to discuss your enhancement. Explain why this enhancement would be useful and provide as much detail as possible.
-   If you have a clear vision, you can also submit a pull request with the enhancement.

### Pull Requests

-   Fork the repository and create your branch from `main`.
-   If you've added code that should be tested, add tests.
-   If you've changed APIs, update the documentation.
-   Ensure the test suite passes (`pytest`).
-   Make sure your code lints (e.g., using Pylance, Flake8, or Black).
-   Issue that pull request!

## Development Setup

(This section can be expanded with more specific setup instructions if needed, e.g., virtual environment setup, specific Python versions, pre-commit hooks.)

1.  Fork the repository.
2.  Clone your fork: `git clone https://github.com/your-username/CIRISEngine.git` (Replace with actual URL)
3.  Create a virtual environment and activate it.
4.  Install dependencies: `pip install -r requirements.txt`
5.  Set up any necessary environment variables (see `README.md`).

## Development Guidelines

### Task and Thought Creation

When integrating new input sources or agents, please adhere to the following conventions for creating Tasks and Thoughts:

-   **Always store raw external input in `Task.context` under a descriptive key, often including an `"initial_input_content"` field for the primary text.**
    For example, when a new Discord message is received, the `Task` object created should have its `context` dictionary populated like this:
    ```python
    task_context = {
        "origin_service": "discord", # Identifies the source service
        "initial_input_content": message.content, # The raw Discord message content
        "discord_message_id": str(message.id),
        "discord_channel_id": str(message.channel.id),
        "discord_user_id": str(message.author.id),
        "discord_user_name": message.author.name,
        # ... other relevant metadata from the source ...
    }
    new_task = Task(..., context=task_context)
    ```
    The `AgentProcessor` uses `Task.description` (which is often derived from `initial_input_content` or a summary) to populate the content of the initial "seed thought".

-   **The engine auto-generates a "seed thought"; do not add initial `Thought`s manually for new tasks.**
    When a new `Task` is added (e.g., via a service handler calling `ActionDispatcher.add_task_to_db()`), the `AgentProcessor._generate_seed_thoughts()` method will automatically detect active tasks needing seeds and generate an initial "seed" thought for it. Your service/input handler code should primarily be responsible for creating and persisting the `Task`.

Adhering to these guidelines ensures consistency in how new work enters the CIRIS Engine processing pipeline.

### Agent Profiles

The CIRIS Engine uses agent profiles (defined in `ciris_engine.core.config_schemas.SerializableAgentProfile`) to define the "personality" and specific configurations for different agent behaviors. This includes specifying the Domain-Specific Decision-Making Algorithm (DSDMA), permitted actions, and prompt overrides for various DMAs.

**Creating a New Profile:**

1.  **Define your DSDMA Class (Optional):**
    *   If your profile requires custom domain-specific logic, create a new Python class that inherits from `ciris_engine.dma.dsdma_base.BaseDSDMA`.
    *   Implement the `evaluate_thought` method and define a `DOMAIN_NAME` and a `DEFAULT_TEMPLATE` for its system prompt.
    *   Ensure your DSDMA class's `__init__` method calls `super().__init__(...)` and accepts `aclient` (the instructor-patched OpenAI client) and `model_name`, plus any `domain_specific_knowledge` or `prompt_template` overrides it might need from `dsdma_kwargs`.
    *   Place this class in a suitable location, e.g., `ciris_engine/dma/dsdma_yournewprofile.py`.
    *   Ensure your new DSDMA class is imported in `ciris_engine/dma/__init__.py` if you want it to be easily accessible.

2.  **Create a Profile YAML File:**
    *   Create a new YAML file in the `ciris_profiles/` directory (e.g., `ciris_profiles/yournewprofile.yaml`).
    *   The YAML file should adhere to the `SerializableAgentProfile` schema:
        ```yaml
        name: YourProfileName # e.g., "Researcher", "HelperBot"
        dsdma_identifier: YourDSDMAClassName # e.g., "StudentDSDMA", "BasicTeacherDSDMA", or null
        dsdma_kwargs: # Optional: Arguments to pass to your DSDMA's __init__
          prompt_template: | # Example: Override the DSDMA's DEFAULT_TEMPLATE
            You are the YourProfileName DSDMA. Your specific instructions go here.
            Context: {context_str}
            Rules: {rules_summary_str}
            Respond in JSON...
          # domain_specific_knowledge:
          #   some_custom_key: "some_value"
        permitted_actions: # List of allowed actions for this profile
          - "speak"
          - "ponder"
          # - "tool"
          # - "reject"
          # - "defer"
        csdma_overrides: # Optional: Overrides for CSDMAEvaluator
          csdma_system_prompt: | # Example: Override CSDMA's system prompt
            You are a CSDMA for the YourProfileName agent. Evaluate common sense with a focus on X.
            Context: {context_summary}
            ... (rest of CSDMA prompt structure)
        action_selection_pdma_overrides: # Optional: Overrides for ActionSelectionPDMA prompts
          system_header: |
            You are acting for the YourProfileName agent. Prioritize X and Y.
          # Example: student_mode_csdma_ambiguity_guidance (if your profile is 'student')
          # yourprofilename_mode_csdma_ambiguity_guidance: |
          #   Guidance for ActionSelectionPDMA on how to react to CSDMA flags for this profile.
          # ... other specific overrides for ActionSelectionPDMA ...
        ```

**Using a Profile:**

1.  **Loading the Profile:**
    *   The `ciris_engine.utils.profile_loader.load_profile(path_to_yaml_file)` function is used to load profiles.
    *   Agent entry points (like `run_discord_student.py`, `run_discord_teacher.py`) are responsible for loading the desired profile.
    *   These scripts also ensure the loaded profile is registered in the `AppConfig.agent_profiles` dictionary, typically keyed by the profile's lowercase name.

2.  **Instantiating Components:**
    *   The loaded `SerializableAgentProfile` object (`agent_profile`) provides:
        *   `agent_profile.name`: The agent's name.
        *   `agent_profile.dsdma_identifier`: String key to look up the DSDMA class in a registry (e.g., `DSDMA_CLASS_REGISTRY` in the run scripts).
        *   `agent_profile.dsdma_kwargs`: Keyword arguments for the DSDMA's constructor.
        *   `agent_profile.permitted_actions`: List of `HandlerActionType` enums.
        *   `agent_profile.csdma_overrides`: Dictionary of overrides for `CSDMAEvaluator`.
        *   `agent_profile.action_selection_pdma_overrides`: Dictionary of overrides for `ActionSelectionPDMAEvaluator`.
    *   These are used during the setup of DMAs in the run scripts. The `WorkflowCoordinator` then uses these instantiated DMAs and the `AppConfig` (which contains the profiles) to manage the processing flow.

By following this structure, you can easily define and integrate new agent personalities into the CIRIS Engine.

## Coding Conventions

-   Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code.
-   Use type hints for all function signatures and complex variable assignments.
-   Write clear and concise commit messages.
-   Ensure code is well-commented, especially for complex logic.
-   Write unit tests for new features and bug fixes.

## Issue and Pull Request Labels

(This section can be expanded if you use specific labels for issues and PRs.)

Thank you for your contributions!
