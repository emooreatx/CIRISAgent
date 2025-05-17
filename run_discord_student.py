import asyncio
import logging
import os
from pathlib import Path # Added import
from typing import Dict, Optional # Added import

# CIRIS Engine Core Components
from ciris_engine.core.config_manager import get_config_async, AppConfig
from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.core.agent_processor import AgentProcessor
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.core.config_schemas import SerializableAgentProfile as AgentProfile # Updated import
from ciris_engine.utils.profile_loader import load_profile

# DMAs and Guardrails
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.dma.dsdma_base import BaseDSDMA # For type hinting and registry
# Example DSDMA implementations (replace with actuals or make registry more robust)
from ciris_engine.dma.dsdma_student import StudentDSDMA 
from ciris_engine.dma.dsdma_teacher import BasicTeacherDSDMA


# Services
from ciris_engine.services.llm_service import LLMService
from ciris_engine.services.discord_service import DiscordService, DiscordConfig

# Utility for logging
from ciris_engine.utils.logging_config import setup_basic_logging

logger = logging.getLogger(__name__)

async def main_student():
    """
    Main function to initialize and run CIRIS Engine with DiscordService using the 'student' profile.
    """
    setup_basic_logging(level=logging.INFO) # Initialize logging
    logger.info("Starting CIRIS Engine with DiscordService (Student Profile)...")

    # --- Configuration Loading ---
    try:
        # app_config will be loaded using the default mechanism in get_config()
        # If a specific file path were needed, load_config_from_file could be used here.
        app_config: AppConfig = await get_config_async()
        logger.info("Application configuration loaded successfully.")
    except Exception as e:
        logger.exception(f"Failed to load application configuration: {e}")
        return

    # --- Load Student Agent Profile ---
    student_profile_name = "student" # Define the profile to load
    agent_profile: Optional[AgentProfile] = None
    try:
        # Assuming profiles are in 'ciris_profiles/<profile_name>.yaml' relative to project root
        # Adjust path if your profiles are located elsewhere
        profile_base_path = app_config.profile_directory # Use the new field from AppConfig
        profile_file_path = os.path.join(profile_base_path, f"{student_profile_name}.yaml")
        
        if not os.path.exists(profile_file_path):
            logger.error(f"Profile file not found: {profile_file_path}. Ensure it exists or check 'agent_profile_path' in config.")
            # Fallback to default profile if student profile is not found
            if "default" in app_config.agent_profiles:
                 # Ensure app_config.agent_profiles["default"] is a SerializableAgentProfile instance
                 # or a dict that can be unpacked into it.
                 default_profile_data = app_config.agent_profiles["default"]
                 if isinstance(default_profile_data, AgentProfile): # AgentProfile is now SerializableAgentProfile
                     agent_profile = default_profile_data
                 elif isinstance(default_profile_data, dict): # If it's still a dict from older config
                     agent_profile = AgentProfile(**default_profile_data)
                 else: # Assuming it's already a SerializableAgentProfile from Pydantic model
                     agent_profile = AgentProfile(**default_profile_data.model_dump())

                 logger.warning(f"Student profile file not found, loaded default profile: {agent_profile.name}")
            else:
                raise FileNotFoundError(f"Student profile '{profile_file_path}' not found and no default profile configured.")
        else:
            agent_profile = await load_profile(Path(profile_file_path))
            if agent_profile:
                logger.info(f"Successfully loaded agent profile: {agent_profile.name} from {profile_file_path}")
            else:
                # load_profile logs error, raise here to stop execution if critical
                raise FileNotFoundError(f"Failed to load student profile from {profile_file_path}, even though file exists.")

    except Exception as e:
        logger.exception(f"Failed to load agent profile '{student_profile_name}': {e}")
        return
    
    if not agent_profile:
        logger.error(f"Agent profile '{student_profile_name}' could not be loaded. Exiting.")
        return
    else:
        # Ensure the loaded profile is in app_config.agent_profiles, keyed by its lowercase name
        # This makes it discoverable by WorkflowCoordinator
        if agent_profile.name.lower() not in app_config.agent_profiles:
            app_config.agent_profiles[agent_profile.name.lower()] = agent_profile
            logger.info(f"Ensured profile '{agent_profile.name}' is available in AppConfig under key '{agent_profile.name.lower()}'.")
        elif app_config.agent_profiles[agent_profile.name.lower()] != agent_profile:
            # If it exists but is different, update it (though this case is less likely here)
            app_config.agent_profiles[agent_profile.name.lower()] = agent_profile
            logger.warning(f"Updated profile '{agent_profile.name}' in AppConfig under key '{agent_profile.name.lower()}'.")


    # --- Initialize Core Components ---
    action_dispatcher = ActionDispatcher()

    # Initialize persistence layer (ensure tables are created)
    try:
        from ciris_engine.core import persistence # Import persistence
        from ciris_engine.core.config_manager import get_sqlite_db_full_path

        # Ensure a clean database for each run of this script
        db_file_path_str = get_sqlite_db_full_path()
        db_file = Path(db_file_path_str)
        if db_file.exists():
            logger.warning(f"Deleting existing database file for a clean run: {db_file}")
            db_file.unlink()

        persistence.initialize_database()
        logger.info(f"Database initialized successfully at {db_file_path_str}.")
    except Exception as e:
        logger.exception(f"Failed to initialize database: {e}")
        return # Stop if DB initialization fails
    
    llm_service = LLMService(llm_config=app_config.llm_services)
    agent_processor = None # Initialize to None for finally block
    services_to_stop = [llm_service]

    try:
        await llm_service.start()
        llm_client = llm_service.get_client()

        # DMAs and Guardrails - using the loaded student profile
        # Ensure the profile contains necessary overrides or uses defaults
        # Model name will come from the llm_client (derived from AppConfig)
        ethical_pdma_evaluator = EthicalPDMAEvaluator( # Removed ethical_pdma_overrides
            aclient=llm_client.instruct_client, 
            model_name=llm_client.model_name # Use model_name from llm_client
        )
        csdma_evaluator = CSDMAEvaluator(
            aclient=llm_client.instruct_client,
            model_name=llm_client.model_name, # Use model_name from llm_client
            prompt_overrides=agent_profile.csdma_overrides # Pass csdma_overrides
        )
        action_selection_pdma_evaluator = ActionSelectionPDMAEvaluator(
            aclient=llm_client.instruct_client, 
            model_name=llm_client.model_name, # Use model_name from llm_client
            prompt_overrides=agent_profile.action_selection_pdma_overrides
        )
        ethical_guardrails = EthicalGuardrails(
            aclient=llm_client.instruct_client, 
            model_name=llm_client.model_name, # Use model_name from llm_client
            guardrails_config=app_config.guardrails # Pass the guardrails_config
        )
        
        # --- DSDMA Instantiation from Profile ---
        dsdma_evaluators: Dict[str, BaseDSDMA] = {}
        # Ensure the registry uses the same keys as dsdma_identifier in profiles
        DSDMA_CLASS_REGISTRY: Dict[str, type[BaseDSDMA]] = {
            "StudentDSDMA": StudentDSDMA, # Key matches profile
            "BasicTeacherDSDMA": BasicTeacherDSDMA,
            # Add other DSDMA class identifiers here
        }

        if agent_profile.dsdma_identifier:
            dsdma_cls = DSDMA_CLASS_REGISTRY.get(agent_profile.dsdma_identifier)
            if dsdma_cls:
                try:
                    # Pass dsdma_kwargs from the profile to the DSDMA constructor
                    dsdma_instance = dsdma_cls(
                        aclient=llm_client.instruct_client,
                        model_name=llm_client.model_name,
                        **(agent_profile.dsdma_kwargs or {}) # Ensure kwargs is a dict
                    )
                    # Key for dsdma_evaluators should match what WorkflowCoordinator expects,
                    # often the profile name itself.
                    dsdma_evaluators[agent_profile.name] = dsdma_instance
                    logger.info(f"DSDMA Evaluator '{agent_profile.name}' (using identifier '{agent_profile.dsdma_identifier}') of type {dsdma_cls.__name__} initialized for student profile.")
                except Exception as e:
                    logger.exception(f"Failed to instantiate DSDMA '{agent_profile.dsdma_identifier}' from student profile '{agent_profile.name}': {e}")
            else:
                logger.warning(f"DSDMA identifier '{agent_profile.dsdma_identifier}' for profile '{agent_profile.name}' not found in DSDMA_CLASS_REGISTRY.")
        else:
            logger.info(f"No DSDMA identifier specified for profile '{agent_profile.name}'. No DSDMA will be used.")


        workflow_coordinator = WorkflowCoordinator(
            llm_client=llm_client,
            ethical_pdma_evaluator=ethical_pdma_evaluator,
            csdma_evaluator=csdma_evaluator,
            action_selection_pdma_evaluator=action_selection_pdma_evaluator,
            ethical_guardrails=ethical_guardrails,
            app_config=app_config,
            dsdma_evaluators=dsdma_evaluators
        )

        agent_processor = AgentProcessor(
            app_config=app_config,
            workflow_coordinator=workflow_coordinator,
            action_dispatcher=action_dispatcher
        )

        # Discord Service
        discord_cfg = DiscordConfig() # Loads from env vars by default
        # Potentially override DiscordConfig with app_config.discord_service_config if defined
        # if hasattr(app_config, "discord_service_config") and app_config.discord_service_config:
        #     discord_cfg = DiscordConfig(**app_config.discord_service_config.model_dump())
            
        discord_service = DiscordService(action_dispatcher=action_dispatcher, config=discord_cfg)
        services_to_stop.append(discord_service)
        
        logger.info("Starting DiscordService and AgentProcessor for STUDENT profile...")
        
        # Start AgentProcessor loop as a background task
        agent_processor_task = asyncio.create_task(agent_processor.start_processing())
        logger.info("AgentProcessor processing loop (student profile) started.")

        # Start DiscordService (this will block if it uses bot.run())
        # Ensure DiscordService.start() uses `await self.bot.start(token)` for non-blocking behavior
        await discord_service.start() 
        
        logger.info("DiscordService (student profile) started. System is live.")
        
        # Keep main alive while agent_processor_task and Discord bot run
        await agent_processor_task

    except Exception as e:
        logger.exception(f"An error occurred during student bot startup or main processing: {e}")
    finally:
        logger.info("Initiating shutdown sequence for student bot...")
        
        if agent_processor and agent_processor._processing_task and not agent_processor._processing_task.done():
            logger.info("Stopping AgentProcessor (student profile)...")
            await agent_processor.stop_processing()
        
        for service in reversed(services_to_stop):
            try:
                logger.info(f"Stopping service: {service.service_name}...")
                await service.stop()
            except Exception as e:
                logger.exception(f"Error stopping service {service.service_name}: {e}")
        
        logger.info("CIRIS Engine (Student Profile) shutdown complete.")

if __name__ == "__main__":
    # Ensure necessary environment variables are set (e.g., OPENAI_API_KEY, DISCORD_BOT_TOKEN)
    # Example check:
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set.")
    elif not os.getenv("DISCORD_BOT_TOKEN"):
        print("Error: DISCORD_BOT_TOKEN environment variable is not set.")
    else:
        try:
            asyncio.run(main_student())
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received. Shutting down student bot...")
        except Exception as e:
            logger.exception(f"Unhandled exception in top-level asyncio.run for student bot: {e}")
        finally:
            logger.info("Student bot application exiting.")
