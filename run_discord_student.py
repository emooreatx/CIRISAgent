import logging
from ciris_engine.utils.logging_config import setup_basic_logging
setup_basic_logging(level=logging.INFO)

import os
from ciris_engine.runtime.base_runtime import BaseRuntime, DiscordAdapter

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SNORE_CHANNEL_ID = os.getenv("SNORE_CHANNEL_ID")
PROFILE_PATH = os.path.join("ciris_profiles", "student.yaml")

if __name__ == "__main__":
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set")
    else:
        runtime = BaseRuntime(
            io_adapter=DiscordAdapter(TOKEN),
            profile_path=PROFILE_PATH,
            snore_channel_id=SNORE_CHANNEL_ID,
        )
        runtime.run()
