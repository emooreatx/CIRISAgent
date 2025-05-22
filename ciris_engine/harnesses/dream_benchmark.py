import asyncio
from typing import List, Dict, Any, Callable

from ciris_engine.services.cirisnode_client import CIRISNodeClient


async def _run_limited(method: Callable[[str, str], asyncio.Future], model_ids: List[str], agent_id: str, limit: int) -> Dict[str, Any]:
    """Run client method concurrently with a limit."""
    semaphore = asyncio.Semaphore(limit)
    results: Dict[str, Any] = {}

    async def _run(model_id: str) -> None:
        async with semaphore:
            results[model_id] = await method(model_id, agent_id)

    await asyncio.gather(*(_run(mid) for mid in model_ids))
    return results


async def run_benchmark_suite(client: CIRISNodeClient, model_ids: List[str], agent_id: str, max_concurrent: int = 10) -> Dict[str, Dict[str, Any]]:
    """Run HE-300 then simplebench for given models under Dream Mode."""
    he300 = await _run_limited(client.run_he300, model_ids, agent_id, max_concurrent)
    simple = await _run_limited(client.run_simplebench, model_ids, agent_id, max_concurrent)
    return {"he300": he300, "simplebench": simple}
