from ciris_engine.processor.dream_processor import DreamProcessor


async def run_dream_session(
    processor: DreamProcessor,
    *,
    duration: float = 60.0,
    pulse_interval: float = 300.0,
) -> dict:
    """Run a dream session and return the final summary."""
    processor.pulse_interval = pulse_interval
    await processor.start_dreaming(duration)
    if processor._dream_task:
        await processor._dream_task
    return processor.get_dream_summary()
