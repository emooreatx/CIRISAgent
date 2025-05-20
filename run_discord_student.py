import asyncio
import os
import logging
from ciris_engine.utils.logging_config import setup_basic_logging

# Import the teacher run script and reuse its main implementation
import run_discord_teacher as teacher_run

setup_basic_logging(level=logging.INFO)

# Override the profile path to use the student profile
teacher_run.PROFILE_PATH = os.path.join("ciris_profiles", "student.yaml")

if __name__ == "__main__":
    asyncio.run(teacher_run.main())
