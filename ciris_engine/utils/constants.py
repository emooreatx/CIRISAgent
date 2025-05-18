import os

DEFAULT_WA = os.getenv("WA_DISCORD_USER", "somecomputerguy")

# Flag indicating that a memory meta-thought should be generated for the
# originating context. It is toggled by the ActionDispatcher when
# external actions occur and cleared once a meta-thought has been enqueued.
NEED_MEMORY_METATHOUGHT = "need_memory_metathought"

