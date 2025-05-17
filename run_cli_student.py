import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from ciris_engine.core.config_manager import get_config_async, AppConfig
from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.core.agent_processor import AgentProcessor
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.core.config_schemas import SerializableAgentProfile as AgentProfile
from ciris_engine.utils.profile_loader import load_profile

from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.dma.dsdma_base import BaseDSDMA
from ciris_engine.dma.dsdma_student import StudentDSDMA
from ciris_engine.dma.dsdma_teacher import BasicTeacherDSDMA

from ciris_engine.services.llm_service import LLMService
from ciris_engine.services.cli_service import CLIService
from ciris_engine.utils.logging_config import setup_basic_logging

logger = logging.getLogger(__name__)


async def main_cli_student():
    setup_basic_logging(level=logging.INFO)
    logger.info("Starting CIRIS Engine CLI (Student Profile)...")

    app_config: AppConfig = await get_config_async()

    profile_base_path = app_config.profile_directory
    profile_file_path = os.path.join(profile_base_path, "student.yaml")
    agent_profile: Optional[AgentProfile] = await load_profile(Path(profile_file_path))
    if not agent_profile:
        raise FileNotFoundError(f"Profile not found: {profile_file_path}")

    if agent_profile.name.lower() not in app_config.agent_profiles:
        app_config.agent_profiles[agent_profile.name.lower()] = agent_profile

    action_dispatcher = ActionDispatcher()

    from ciris_engine.core import persistence
    from ciris_engine.core.config_manager import get_sqlite_db_full_path

    db_file_path_str = get_sqlite_db_full_path()
    db_file = Path(db_file_path_str)
    if db_file.exists():
        logger.warning("Deleting existing database for clean CLI run: %s", db_file)
        db_file.unlink()

    persistence.initialize_database()

    llm_service = LLMService(llm_config=app_config.llm_services)
    await llm_service.start()
    llm_client = llm_service.get_client()

    ethical_pdma_evaluator = EthicalPDMAEvaluator(
        aclient=llm_client.instruct_client,
        model_name=llm_client.model_name,
    )
    csdma_evaluator = CSDMAEvaluator(
        aclient=llm_client.instruct_client,
        model_name=llm_client.model_name,
        prompt_overrides=agent_profile.csdma_overrides,
    )
    action_selection_pdma_evaluator = ActionSelectionPDMAEvaluator(
        aclient=llm_client.instruct_client,
        model_name=llm_client.model_name,
        prompt_overrides=agent_profile.action_selection_pdma_overrides,
    )
    ethical_guardrails = EthicalGuardrails(
        aclient=llm_client.instruct_client,
        model_name=llm_client.model_name,
        guardrails_config=app_config.guardrails,
    )

    dsdma_evaluators: Dict[str, BaseDSDMA] = {}
    DSDMA_CLASS_REGISTRY: Dict[str, type[BaseDSDMA]] = {
        "StudentDSDMA": StudentDSDMA,
        "BasicTeacherDSDMA": BasicTeacherDSDMA,
    }
    if agent_profile.dsdma_identifier:
        dsdma_cls = DSDMA_CLASS_REGISTRY.get(agent_profile.dsdma_identifier)
        if dsdma_cls:
            dsdma_instance = dsdma_cls(
                aclient=llm_client.instruct_client,
                model_name=llm_client.model_name,
                **(agent_profile.dsdma_kwargs or {}),
            )
            dsdma_evaluators[agent_profile.name] = dsdma_instance

    workflow_coordinator = WorkflowCoordinator(
        llm_client=llm_client,
        ethical_pdma_evaluator=ethical_pdma_evaluator,
        csdma_evaluator=csdma_evaluator,
        action_selection_pdma_evaluator=action_selection_pdma_evaluator,
        ethical_guardrails=ethical_guardrails,
        app_config=app_config,
        dsdma_evaluators=dsdma_evaluators,
    )

    agent_processor = AgentProcessor(
        app_config=app_config,
        workflow_coordinator=workflow_coordinator,
        action_dispatcher=action_dispatcher,
    )

    cli_service = CLIService(action_dispatcher=action_dispatcher)

    agent_processor_task = asyncio.create_task(agent_processor.start_processing())
    await cli_service.start()
    await agent_processor_task

    await cli_service.stop()
    await llm_service.stop()


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set.")
    else:
        try:
            asyncio.run(main_cli_student())
        except KeyboardInterrupt:
            logger.info("CLI run interrupted by user.")

