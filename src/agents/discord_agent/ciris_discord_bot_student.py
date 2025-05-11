# src/agents/discord_agent/ciris_discord_bot_student.py
import asyncio
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import json

import discord # type: ignore
from openai import AsyncOpenAI
import instructor

# Existing CIRIS Engine imports
from ciris_engine.core.data_schemas import (
    Task, Thought, ThoughtQueueItem, TaskStatus, ThoughtStatus, ThoughtType,
    HandlerActionType, ActionSelectionPDMAResult # Added ActionSelectionPDMAResult for type hint
)
from ciris_engine.core.config import (
    SQLITE_DB_PATH,
    DEFAULT_OPENAI_MODEL_NAME,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    DEFAULT_OPENAI_MAX_RETRIES
)
from ciris_engine.core.thought_queue_manager import ThoughtQueueManager
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.dma import (
    EthicalPDMAEvaluator,
    CSDMAEvaluator,
    # BasicTeacherDSDMA, # Will be loaded via profile
    ActionSelectionPDMAEvaluator
)
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.utils.logging_config import setup_basic_logging
from ciris_engine.utils.profile_loader import load_profile 
from ciris_engine.agent_profile import AgentProfile 
# DSDMA classes like BasicTeacherDSDMA or StudentDSDMA will be loaded dynamically

# New imports for Discord integration
from .config import DiscordConfig # Relative import assuming it's in the same directory
from .action_handlers import (
    handle_discord_speak,
    handle_discord_deferral
)

# Pydantic/Instructor exceptions
from instructor.exceptions import InstructorRetryException
from pydantic import ValidationError

# Global logger
logger = logging.getLogger(__name__) # Consider renaming logger if both bots run in same process space
                                     # e.g., logger = logging.getLogger("ciris_discord_bot_student")

def serialize_discord_message(message):
    """
    Safely serialize a Discord message to a JSON-compatible dictionary.
    
    Args:
        message: Discord Message object
        
    Returns:
        dict: JSON-serializable representation of the message
    """
    if not message:
        return None
        
    return {
        'id': str(message.id),
        'content': message.content,
        'author': {
            'id': str(message.author.id),
            'name': message.author.name,
            'discriminator': message.author.discriminator if hasattr(message.author, 'discriminator') else None,
        },
        'channel_id': str(message.channel.id),
        'channel_name': getattr(message.channel, 'name', 'DM'),
        'guild_id': str(message.guild.id) if message.guild else None,
        'timestamp': message.created_at.isoformat() if message.created_at else None,
    }

class CIRISDiscordStudentBot: # Renamed class
    """
    Combines CIRIS Engine processing with Discord bot functionality, using STUDENT profile.
    """
    def __init__(self):
        self.discord_config = DiscordConfig()
        if not self.discord_config.validate(): # type: ignore
            logger.critical("Discord configuration validation failed. Exiting.")
            raise ValueError("Invalid Discord Configuration")

        # Initialize Discord client
        intents = discord.Intents.default() 
        intents.messages = True
        intents.message_content = True 
        intents.guilds = True
        self.client = discord.Client(intents=intents)

        # Initialize CIRIS Engine components
        self.thought_manager: Optional[ThoughtQueueManager] = None
        self.coordinator: Optional[WorkflowCoordinator] = None
        self.configured_aclient: Optional[instructor.Instructor] = None
        
        self._setup_ciris_engine_components()
        self._register_discord_events()

    def _setup_ciris_engine_components(self):
        """Initializes all CIRIS engine components."""
        logger.info("Setting up CIRIS Engine components for STUDENT Bot...") # Modified log
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        openai_api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1") 
        model_name = os.environ.get("OPENAI_MODEL_NAME", DEFAULT_OPENAI_MODEL_NAME)

        if not openai_api_key:
            logger.critical("OPENAI_API_KEY environment variable not set. CIRIS Engine cannot start.")
            raise ValueError("OPENAI_API_KEY not set.")

        raw_openai_client = AsyncOpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base,
            timeout=DEFAULT_OPENAI_TIMEOUT_SECONDS,
            max_retries=DEFAULT_OPENAI_MAX_RETRIES
        )
        self.configured_aclient = instructor.patch(raw_openai_client, mode=instructor.Mode.JSON)
        
        logger.info(f"Instructor-patched AsyncOpenAI client created for Discord STUDENT Bot (Mode: JSON). API Base: {self.configured_aclient.base_url}, Model: {model_name}, Timeout: {DEFAULT_OPENAI_TIMEOUT_SECONDS}s, Max Retries: {DEFAULT_OPENAI_MAX_RETRIES}.")

        db_path_for_run = SQLITE_DB_PATH
        self.thought_manager = ThoughtQueueManager(db_path=db_path_for_run)
        logger.info(f"ThoughtQueueManager initialized with DB at {db_path_for_run}.")

        if not self.configured_aclient: 
            logger.critical("AsyncOpenAI client not configured. Cannot initialize DMAs.")
            raise ValueError("AsyncOpenAI client not configured.")

        ethical_pdma = EthicalPDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        csdma = CSDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        
        # --- Load Agent Profile for Discord Bot ---
        discord_bot_profile_name = "student" # MODIFIED: Explicitly set to "student"
        profile_path = f"ciris_profiles/{discord_bot_profile_name}.yaml"
        try:
            profile = load_profile(profile_path)
            logger.info(f"Discord STUDENT Bot: Successfully loaded agent profile: {profile.name} from {profile_path}")
        except Exception as e:
            logger.critical(f"Discord STUDENT Bot: Failed to load agent profile from {profile_path}: {e}", exc_info=True)
            raise ValueError(f"Discord STUDENT Bot ProfileLoadError: {e}") from e

        try:
            dsdma_instance = profile.dsdma_cls(
                aclient=self.configured_aclient,
                model_name=model_name, 
                **profile.dsdma_kwargs 
            )
            dsdma_evaluators = {profile.name: dsdma_instance}
            logger.info(f"Discord STUDENT Bot: DSDMA Evaluator '{profile.name}' of type {profile.dsdma_cls.__name__} initialized using profile.")
        except Exception as e:
            logger.critical(f"Discord STUDENT Bot: Failed to instantiate DSDMA from profile {profile.name}: {e}", exc_info=True)
            raise ValueError(f"Discord STUDENT Bot DSDMAInstantiationError: {e}") from e

        action_selection_pdma = ActionSelectionPDMAEvaluator(
            aclient=self.configured_aclient, 
            model_name=model_name,
            prompt_overrides=profile.action_prompt_overrides
        )
        
        guardrails = EthicalGuardrails(aclient=self.configured_aclient, model_name=model_name)
        logger.info("Discord STUDENT Bot: DMA Evaluators and Guardrails initialized with profile.")

        self.coordinator = WorkflowCoordinator(
            llm_client=None, 
            ethical_pdma_evaluator=ethical_pdma,
            csdma_evaluator=csdma,
            dsdma_evaluators=dsdma_evaluators,
            action_selection_pdma_evaluator=action_selection_pdma,
            ethical_guardrails=guardrails,
            thought_queue_manager=self.thought_manager
        )
        logger.info("WorkflowCoordinator and all DMAs/Guardrails initialized for STUDENT Bot.")

    def _register_discord_events(self):
        """Registers event handlers for the Discord client."""
        @self.client.event
        async def on_ready():
            if not self.client.user:
                logger.error("Discord client user not found on_ready.")
                return
            logger.info(f'STUDENT Bot Logged in as {self.client.user.name} ({self.client.user.id})') # Modified log
            if hasattr(self.discord_config, 'log_config') and callable(self.discord_config.log_config):
                self.discord_config.log_config() 
            
            self.client.loop.create_task(self.continuous_thought_processing_loop())


        @self.client.event
        async def on_message(message: discord.Message):
            if not self._should_process_discord_message(message):
                return

            channel_name = message.channel.name if hasattr(message.channel, 'name') else 'DM'
            logger.info(f"STUDENT Bot Received message from {message.author.name} in #{channel_name}: '{message.content[:50]}...'") # Modified log
            
            if not self.thought_manager:
                logger.error("ThoughtQueueManager not initialized. Cannot process message.")
                return

            task_description = f"Process Discord message from {message.author.name} in #{channel_name} (Student Bot): {message.content[:30]}..."
            
            task_context = {
                "initial_input_content": message.content,
                "environment": "discord_student_bot", 
                "channel": channel_name,
                "agent_name": "CIRIS Student Bot", # Or derive from profile
                "discord_message_id": str(message.id),
                "discord_channel_id": str(message.channel.id),
                "discord_author_id": str(message.author.id),
                "discord_author_name": message.author.name,
                "discord_guild_id": str(message.guild.id) if message.guild else None,
                "discord_message_obj_serialized": serialize_discord_message(message)
            }

            new_task = Task(
                task_id=f"task_msg_{message.id}_student", 
                description=task_description,
                priority=1,
                status=TaskStatus(status="active"),
                context=task_context
            )

            try:
                self.thought_manager.add_task(new_task)
                logger.info(f"STUDENT Bot: Added new task ID {new_task.task_id} for Discord message {message.id}. Seed thought will be auto-generated.")
            except Exception as e:
                logger.error(f"STUDENT Bot: Failed to add task for Discord message {message.id}: {e}")
                return
            
            # NOTE: Explicit Thought creation is removed.

    def _should_process_discord_message(self, message: discord.Message) -> bool:
        # This logic can be identical to the other bot, or customized if needed.
        # For now, keeping it the same.
        if not self.client.user: return False 
        if message.author == self.client.user:
            return False
        if self.discord_config.server_id_int and message.guild and message.guild.id != self.discord_config.server_id_int:
            logger.debug(f"Message from {message.author.name} ignored by STUDENT Bot: wrong server ID ({message.guild.id}).")
            return False
        is_dm = isinstance(message.channel, discord.DMChannel)
        if self.discord_config.target_channels_set:
            if is_dm:
                logger.debug(f"DM from {message.author.name} ignored by STUDENT Bot: target channels are set.")
                return False
            elif message.channel.id not in self.discord_config.target_channels_set:
                logger.debug(f"Message from {message.author.name} in #{message.channel.name if hasattr(message.channel, 'name') else 'UnknownChannel'} ignored by STUDENT Bot: not in target channels.")
                return False
        else: # No specific target channels, listen for mentions or DMs
            if not is_dm and not self.client.user.mentioned_in(message):
                logger.debug(f"Message from {message.author.name} in #{message.channel.name if hasattr(message.channel, 'name') else 'UnknownChannel'} ignored by STUDENT Bot: no specific channels and bot not mentioned.")
                return False
        return True

    async def continuous_thought_processing_loop(self, max_script_cycles_overall: Optional[int] = None):
        await self.client.wait_until_ready()
        logger.info("--- Starting CIRIS Engine Continuous Thought Processing Loop (STUDENT Bot) ---")
        
        script_cycle_count = 0
        while not self.client.is_closed():
            script_cycle_count += 1
            if max_script_cycles_overall and script_cycle_count > max_script_cycles_overall:
                logger.info(f"Reached max overall script cycles ({max_script_cycles_overall}) for STUDENT Bot. Stopping.")
                break
            
            if not self.thought_manager or not self.coordinator:
                logger.error("ThoughtManager or Coordinator not initialized for STUDENT Bot. Waiting...")
                await asyncio.sleep(5)
                continue

            current_processing_round = script_cycle_count
            self.thought_manager.current_round_number = current_processing_round
            
            logger.debug(f"STUDENT Bot Processing Loop Cycle {script_cycle_count}: Populating queue for round {current_processing_round}.")
            self.thought_manager.populate_round_queue(round_number=current_processing_round, max_items=1)

            if not self.thought_manager.current_round_queue:
                await asyncio.sleep(self.discord_config.queue_check_interval_seconds if hasattr(self.discord_config, 'queue_check_interval_seconds') else 5)
                continue

            queued_thought_item = self.thought_manager.get_next_thought_from_queue()
            if not queued_thought_item:
                await asyncio.sleep(1)
                continue

            logger.info(f"STUDENT Bot Cycle {script_cycle_count}: Processing thought ID {queued_thought_item.thought_id} - Content: {str(queued_thought_item.content)[:60]}...")
            
            if not (queued_thought_item.initial_context and \
                    queued_thought_item.initial_context.get("discord_message_obj_serialized") and \
                    queued_thought_item.initial_context.get("discord_message_obj_serialized").get("channel_id")):
                logger.error(f"STUDENT Bot Thought {queued_thought_item.thought_id} is missing 'discord_message_obj_serialized' or critical fields within its initial_context. Cannot process for Discord actions.")
                self.thought_manager.update_thought_status(
                    queued_thought_item.thought_id, ThoughtStatus(status="failed"), current_processing_round, 
                    {"error": "Missing or incomplete discord_message_obj_serialized in thought's initial_context"}
                )
                continue
            
            original_discord_message_obj_dict = queued_thought_item.initial_context["discord_message_obj_serialized"]

            final_action_result: Optional[ActionSelectionPDMAResult] = None
            try:
                final_action_result = await self.coordinator.process_thought(
                    thought_item=queued_thought_item,
                    current_platform_context=queued_thought_item.initial_context,
                    benchmark_mode=False 
                )
            except InstructorRetryException as e_instr:
                error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
                logger.error(f"CRITICAL (STUDENT Bot Cycle {script_cycle_count}): InstructorRetryException for thought {queued_thought_item.thought_id}: {error_detail}", exc_info=True)
                self.thought_manager.update_thought_status(
                    queued_thought_item.thought_id, ThoughtStatus(status="failed"), script_cycle_count, {"error": f"InstructorRetryException: {error_detail}"}
                )
            except ValidationError as e_pyd:
                error_detail = e_pyd.errors() if hasattr(e_pyd, 'errors') else str(e_pyd)
                logger.error(f"CRITICAL (STUDENT Bot Cycle {script_cycle_count}): Pydantic ValidationError for thought {queued_thought_item.thought_id}: {error_detail}", exc_info=True)
                self.thought_manager.update_thought_status(
                    queued_thought_item.thought_id, ThoughtStatus(status="failed"), script_cycle_count, {"error": f"Pydantic ValidationError: {error_detail}"}
                )
            except Exception as e_gen:
                logger.error(f"CRITICAL (STUDENT Bot Cycle {script_cycle_count}): General Exception for thought {queued_thought_item.thought_id}: {e_gen}", exc_info=True)
                self.thought_manager.update_thought_status(
                    queued_thought_item.thought_id, ThoughtStatus(status="failed"), script_cycle_count, {"error": f"General Exception: {e_gen}"}
                )

            if final_action_result is None: 
                logger.info(f"STUDENT Bot Cycle {script_cycle_count}: Thought {queued_thought_item.thought_id} was re-queued for Ponder by coordinator.")
                # ... (logging for ponder state can be added if needed)
            elif final_action_result:
                logger.info(f"--- STUDENT Bot Cycle {script_cycle_count}: Final Action Result for thought {queued_thought_item.thought_id} ---")
                logger.info(f"Selected Action: {final_action_result.selected_handler_action.value}")
                logger.info(f"Action Parameters: {final_action_result.action_parameters}")

                action_type = final_action_result.selected_handler_action
                action_params = final_action_result.action_parameters if final_action_result.action_parameters else {}

                if action_type == HandlerActionType.SPEAK:
                    logger.info(f"STUDENT Bot Dispatching SPEAK action for thought {queued_thought_item.thought_id} to Discord handler.")
                    await handle_discord_speak(
                        self.client,
                        original_discord_message_obj_dict, # Pass the dict
                        action_params.get("message_content", "No message content specified.")
                    )
                elif action_type == HandlerActionType.DEFER_TO_WA:
                    logger.info(f"STUDENT Bot Dispatching DEFER_TO_WA action for thought {queued_thought_item.thought_id} to Discord handler.")
                    await handle_discord_deferral(
                        self.client,
                        original_discord_message_obj_dict, # Pass the dict
                        action_params, 
                        str(self.discord_config.deferral_channel_id) 
                    )
                elif action_type == HandlerActionType.PONDER: 
                    logger.error(f"STUDENT Bot Cycle {script_cycle_count}: Thought {queued_thought_item.thought_id} - PONDER action returned by coordinator, but re-queue failed. Treating as DEFER_TO_WA.")
                    await handle_discord_deferral(
                        self.client, 
                        original_discord_message_obj_dict, # Pass the dict
                        {"reason": "Ponder re-queue failed in coordinator.", **action_params}, 
                        str(self.discord_config.deferral_channel_id)
                    )
                    self.thought_manager.update_thought_status(
                        thought_id=queued_thought_item.thought_id,
                        new_status=ThoughtStatus(status="deferred"),
                        round_processed=current_processing_round,
                        processing_result={"status": "Ponder re-queue failed, deferred.", "original_action": final_action_result.model_dump()}
                    )
                    continue 
                elif action_type == HandlerActionType.REJECT_THOUGHT:
                    logger.info(f"STUDENT Bot Cycle {script_cycle_count}: Thought {queued_thought_item.thought_id} REJECTED. Rationale: {action_params.get('reason', 'N/A')}")
                
                if action_type != HandlerActionType.PONDER: 
                    self.thought_manager.update_thought_status(
                        thought_id=queued_thought_item.thought_id,
                        new_status=ThoughtStatus(status="processed"),
                        round_processed=current_processing_round,
                        processing_result=final_action_result.model_dump()
                    )
            await asyncio.sleep(0.2)

        logger.info(f"--- CIRIS Engine Continuous Thought Processing Loop (STUDENT Bot) has ended ---")

    def run(self):
        """Starts the Discord bot."""
        if not self.discord_config.token:
            logger.critical("Discord bot token not found. Cannot start STUDENT Bot.")
            return
        
        logger.info("Starting Discord client for STUDENT Bot...")
        try:
            self.client.run(self.discord_config.token)
        except discord.LoginFailure:
            logger.error("Discord login failed for STUDENT Bot. Check your DISCORD_BOT_TOKEN.")
        except Exception as e:
            logger.critical(f"An error occurred while running the Discord client for STUDENT Bot: {e}", exc_info=True)

if __name__ == "__main__":
    # Setup unique logger for student bot if run directly
    # This helps differentiate logs if both teacher and student bots are run from their respective files.
    student_bot_logger = logging.getLogger() # Get root logger to configure
    # Or, if you want a specific logger for this script:
    # student_bot_logger = logging.getLogger("ciris_discord_bot_student_main")
    setup_basic_logging(logger_instance=student_bot_logger, level=logging.INFO, prefix="[STUDENT_BOT_MAIN]")
    
    if not os.environ.get("OPENAI_API_KEY"):
        student_bot_logger.error("Error: OPENAI_API_KEY environment variable not set.")
    elif not os.environ.get("DISCORD_BOT_TOKEN"): # Assuming student bot uses the same token for now
        student_bot_logger.error("Error: DISCORD_BOT_TOKEN environment variable not set.")
    else:
        bot_engine = CIRISDiscordStudentBot()
        bot_engine.run()
