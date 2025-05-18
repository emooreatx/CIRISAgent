import os
from ciris_engine.runtime import BaseRuntime, CLIAdapter

PROFILE_PATH = os.path.join("ciris_profiles", "teacher.yaml")

if __name__ == "__main__":
    runtime = BaseRuntime(io_adapter=CLIAdapter(), profile_path=PROFILE_PATH)
    runtime.run()
