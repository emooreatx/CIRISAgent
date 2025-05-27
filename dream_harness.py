#!/usr/bin/env python3
"""
CLI utility to run CIRISAgent dream mode, integrating with CIRISNode (FastAPI) to run HE-300 and simplebench.
Each snore pulse summarizes the most recent topics/results in a fun way.
"""
import asyncio
import logging
import argparse
import httpx
from datetime import datetime
from ciris_engine.core import persistence
from ciris_engine.core.config_manager import get_config_async
from ciris_engine.utils.profile_loader import load_profile
from ciris_engine.services.llm_service import LLMService
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.core.action_handlers import (
    ActionHandlerDependencies, SpeakHandler, DeferHandler, RejectHandler, ObserveHandler, MemorizeHandler, ToolHandler, TaskCompleteHandler
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.core.processor import AgentProcessor
from ciris_engine.runtime.base_runtime import BaseRuntime, CLIAdapter
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
import instructor
from ciris_engine.guardrails import EthicalGuardrails

class CIRISNodeClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient()

    async def run_he300(self):
        resp = await self.client.post(f"{self.base_url}/bench/he300")
        resp.raise_for_status()
        return resp.json()

    async def run_simplebench(self):
        resp = await self.client.post(f"{self.base_url}/bench/simplebench")
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()

async def dream_harness(args):
    logging.basicConfig(level=logging.INFO)
    persistence.initialize_database()
    app_config = await get_config_async()
    profile_path = "ciris_profiles/teacher.yaml"
    profile = await load_profile(profile_path)
    if not profile:
        raise FileNotFoundError(profile_path)
    if profile.name.lower() not in app_config.agent_profiles:
        app_config.agent_profiles[profile.name.lower()] = profile

    llm_service = LLMService(app_config.llm_services)
    memory_service = CIRISLocalGraph()
    await llm_service.start()
    await memory_service.start()
    llm_client = llm_service.get_client()

    action_handler_deps = ActionHandlerDependencies(
        action_sink=None,
        memory_service=memory_service,
        observer_service=None,
        io_adapter=None,
        deferral_sink=None,
    )
    speak_handler = SpeakHandler(action_handler_deps)
    defer_handler = DeferHandler(action_handler_deps)
    reject_handler = RejectHandler(action_handler_deps)
    observe_handler = ObserveHandler(action_handler_deps)
    memorize_handler = MemorizeHandler(action_handler_deps)
    tool_handler = ToolHandler(action_handler_deps)
    task_complete_handler = TaskCompleteHandler(action_handler_deps)
    handlers_map = {
        HandlerActionType.SPEAK: speak_handler,
        HandlerActionType.DEFER: defer_handler,
        HandlerActionType.REJECT: reject_handler,
        HandlerActionType.OBSERVE: observe_handler,
        HandlerActionType.MEMORIZE: memorize_handler,
        HandlerActionType.TOOL: tool_handler,
        HandlerActionType.TASK_COMPLETE: task_complete_handler,
    }
    action_dispatcher = ActionDispatcher(handlers=handlers_map)

    ethical_pdma = EthicalPDMAEvaluator(
        aclient=llm_client.instruct_client, model_name=llm_client.model_name,
        max_retries=app_config.llm_services.openai.max_retries
    )
    csdma = CSDMAEvaluator(
        aclient=llm_client.client, model_name=llm_client.model_name,
        max_retries=app_config.llm_services.openai.max_retries
    )
    action_pdma = ActionSelectionPDMAEvaluator(
        aclient=llm_client.client, model_name=llm_client.model_name,
        max_retries=app_config.llm_services.openai.max_retries,
        prompt_overrides=profile.action_selection_pdma_overrides,
        instructor_mode=instructor.Mode[app_config.llm_services.openai.instructor_mode.upper()]
    )
    guardrails = EthicalGuardrails(
        llm_client.instruct_client, app_config.guardrails, model_name=llm_client.model_name
    )

    workflow_coordinator = WorkflowCoordinator(
        llm_client=llm_client.client,
        ethical_pdma_evaluator=ethical_pdma,
        csdma_evaluator=csdma,
        action_selection_pdma_evaluator=action_pdma,
        ethical_guardrails=guardrails,
        app_config=app_config,
        dsdma_evaluators={},
        memory_service=memory_service,
    )
    action_dispatcher = ActionDispatcher(handlers=handlers_map)
    runtime = BaseRuntime(
        io_adapter=CLIAdapter(),
        profile_path=profile_path,
        action_dispatcher=action_dispatcher,
        snore_channel_id="console",
    )

    cirisnode = CIRISNodeClient(args.cirisnode_url)
    pulse = 0
    snore_history = []
    start_time = datetime.now()
    try:
        print(f"[Dream] Starting dream mode for {args.duration} seconds, pulse interval {args.pulse_interval} seconds.")
        end_time = asyncio.get_event_loop().time() + args.duration
        while asyncio.get_event_loop().time() < end_time:
            pulse += 1
            he300_result = await cirisnode.run_he300()
            simplebench_result = await cirisnode.run_simplebench()
            topic = he300_result.get('topic', 'Unknown')
            bench_score = simplebench_result.get('score', 'N/A')
            snore_summary = f"*snore* pulse {pulse}: Dreamt about '{topic}', bench score: {bench_score}!"
            snore_history.append(snore_summary)
            if len(snore_history) > 5:
                snore_history.pop(0)
            print(snore_summary)
            # Fun summary of recent topics
            if pulse % 3 == 0:
                recent = '; '.join(snore_history)
                print(f"[Dream] Recent dream topics: {recent}")
            await asyncio.sleep(args.pulse_interval)
        print("[Dream] Dream ended. Sweet dreams!")
    finally:
        await cirisnode.close()
        await llm_service.stop()
        await memory_service.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CIRISAgent Dream Mode Harness")
    parser.add_argument('--duration', type=float, default=600, help='Dream duration in seconds (default: 600)')
    parser.add_argument('--pulse-interval', type=float, default=60, help='Snore pulse interval in seconds (default: 60)')
    parser.add_argument('--cirisnode-url', type=str, default='http://localhost:8001', help='CIRISNode FastAPI base URL')
    args = parser.parse_args()
    asyncio.run(dream_harness(args))
