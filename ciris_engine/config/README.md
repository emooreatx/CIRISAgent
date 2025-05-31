# config

This module contains configuration utilities for the CIRIS engine.

* `config_loader.py` provides `ConfigLoader.load_config` for loading YAML based
  configuration files and merging them with agent profiles and environment
  variables.
* `dynamic_config.py` implements a lightweight `ConfigManager` that can update
  configuration values at runtime and reload agent profiles.
* `config_manager.py` retains the original JSON helpers used in tests.
