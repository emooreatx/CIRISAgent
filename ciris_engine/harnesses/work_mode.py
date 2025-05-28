from typing import List

from ciris_engine.processor.work_processor import WorkProcessor


async def run_work_rounds(processor: WorkProcessor, rounds: int = 1) -> List[dict]:
    """Run a number of work rounds and return the metrics for each."""
    await processor.initialize()
    results = []
    for i in range(rounds):
        results.append(await processor.process(i))
    await processor.cleanup()
    return results
