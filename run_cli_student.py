import os
from ciris_engine.runtime import BaseRuntime, CLIAdapter
from ciris_engine.utils.logging_config import setup_basic_logging

PROFILE_PATH = os.path.join("ciris_profiles", "student.yaml")

if __name__ == "__main__":
    setup_basic_logging()
    runtime = BaseRuntime(io_adapter=CLIAdapter(), profile_path=PROFILE_PATH)
    runtime.run()
