# src/agents/discord_agent/ciris_discord_bot_alpha.py
import asyncio
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

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
    BasicTeacherDSDMA,
    ActionSelectionPDMAEvaluator
)
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.utils.logging_config import setup_basic_logging

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
logger = logging.getLogger(__name__)

class CIRISDiscordEngineBot:
    """
    Combines CIRIS Engine processing with Discord bot functionality.
    """
    def __init__(self):
        self.discord_config = DiscordConfig()
        if not self.discord_config.validate(): # type: ignore
            logger.critical("Discord configuration validation failed. Exiting.")
            raise ValueError("Invalid Discord Configuration")

        # Initialize Discord client
        intents = discord.Intents.default() # Using default intents
        intents.messages = True
        intents.message_content = True # Ensure this is enabled in your bot's settings
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
        logger.info("Setting up CIRIS Engine components...")
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        model_name = os.environ.get("OPENAI_MODEL_NAME", DEFAULT_OPENAI_MODEL_NAME)

        if not openai_api_key:
            logger.critical("OPENAI_API_KEY environment variable not set. CIRIS Engine cannot start.")
            raise ValueError("OPENAI_API_KEY not set.")

        self.configured_aclient = instructor.patch(AsyncOpenAI(
            timeout=DEFAULT_OPENAI_TIMEOUT_SECONDS,
            max_retries=DEFAULT_OPENAI_MAX_RETRIES
        ))
        logger.info(f"Instructor-patched AsyncOpenAI client configured.")

        db_path_for_run = SQLITE_DB_PATH
        self.thought_manager = ThoughtQueueManager(db_path=db_path_for_run)
        logger.info(f"ThoughtQueueManager initialized with DB at {db_path_for_run}.")

        if not self.configured_aclient: # Should not happen if OPENAI_API_KEY is set
            logger.critical("AsyncOpenAI client not configured. Cannot initialize DMAs.")
            raise ValueError("AsyncOpenAI client not configured.")

        ethical_pdma = EthicalPDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        csdma = CSDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        teacher_dsdma = BasicTeacherDSDMA(aclient=self.configured_aclient, model_name=model_name)
        dsdma_evaluators = {"BasicTeacherMod": teacher_dsdma}
        action_selection_pdma = ActionSelectionPDMAEvaluator(aclient=self.configured_aclient, model_name=model_name)
        guardrails = EthicalGuardrails(aclient=self.configured_aclient, model_name=model_name)

        self.coordinator = WorkflowCoordinator(
            llm_client=None, 
            ethical_pdma_evaluator=ethical_pdma,
            csdma_evaluator=csdma,
            dsdma_evaluators=dsdma_evaluators,
            action_selection_pdma_evaluator=action_selection_pdma,
            ethical_guardrails=guardrails,
            thought_queue_manager=self.thought_manager
        )
        logger.info("WorkflowCoordinator and all DMAs/Guardrails initialized.")

    def _register_discord_events(self):
        """Registers event handlers for the Discord client."""
        @self.client.event
        async def on_ready():
            if not self.client.user:
                logger.error("Discord client user not found on_ready.")
                return
            logger.info(f'Logged in as {self.client.user.name} ({self.client.user.id})')
            if hasattr(self.discord_config, 'log_config') and callable(self.discord_config.log_config):
                self.discord_config.log_config() 
            
            self.client.loop.create_task(self.continuous_thought_processing_loop())


        @self.client.event
        async def on_message(message: discord.Message):
            if not self._should_process_discord_message(message):
                return

            channel_name = message.channel.name if hasattr(message.channel, 'name') else 'DM'
            logger.info(f"Received message from {message.author.name} in #{channel_name}: '{message.content[:50]}...'")
            
            if not self.thought_manager:
                logger.error("ThoughtQueueManager not initialized. Cannot process message.")
                return

            task_description = f"Process message from {message.author.name} in #{channel_name}"
            temp_task = Task(
                task_id=f"task_for_msg_{message.id}",
                description=task_description,
                priority=1,
                status=TaskStatus(status="active"),
                context={"discord_message_id": str(message.id), "channel_id": str(message.channel.id)}
            )
            source_task_id: str
            try:
                self.thought_manager.add_task(temp_task)
                source_task_id = temp_task.task_id
            except Exception as e:
                logger.error(f"Failed to add temporary task for message {message.id}: {e}. Skipping thought creation.")
                return

            initial_thought_context: Dict[str, Any] = {
                "discord_message_obj": message, 
                "discord_message_id": str(message.id),
                "discord_channel_id": str(message.channel.id),
                "discord_channel_name": channel_name,
                "discord_author_id": str(message.author.id),
                "discord_author_name": message.author.name,
                "discord_guild_id": str(message.guild.id) if message.guild else None,
                "environment": "discord"
            }

            new_thought = Thought(
                source_task_id=source_task_id,
                thought_type=ThoughtType(type="thought"),
                content=message.content,
                priority=1,
                status=ThoughtStatus(status="pending"),
                round_created=self.thought_manager.current_round_number,
                processing_context=initial_thought_context
            )

            try:
                self.thought_manager.add_thought(new_thought)
                logger.info(f"Added new thought ID {new_thought.thought_id} from Discord message {message.id} to queue.")
            except Exception as e:
                logger.error(f"Failed to add thought from Discord message {message.id}: {e}")

    def _should_process_discord_message(self, message: discord.Message) -> bool:
        if not self.client.user: return False # Client not ready
        if message.author == self.client.user:
            return False
        if self.discord_config.server_id_int and message.guild and message.guild.id != self.discord_config.server_id_int:
            logger.debug(f"Message from {message.author.name} ignored: wrong server ID ({message.guild.id}).")
            return False
        is_dm = isinstance(message.channel, discord.DMChannel)
        if self.discord_config.target_channels_set:
            if is_dm:
                logger.debug(f"DM from {message.author.name} ignored: target channels are set.")
                return False
            elif message.channel.id not in self.discord_config.target_channels_set:
                logger.debug(f"Message from {message.author.name} in #{message.channel.name if hasattr(message.channel, 'name') else 'UnknownChannel'} ignored: not in target channels.")
                return False
        else:
            if not is_dm and not self.client.user.mentioned_in(message):
                logger.debug(f"Message from {message.author.name} in #{message.channel.name if hasattr(message.channel, 'name') else 'UnknownChannel'} ignored: no specific channels and bot not mentioned.")
                return False
        return True

    async def continuous_thought_processing_loop(self, max_script_cycles_overall: Optional[int] = None):
        await self.client.wait_until_ready()
        logger.info("--- Starting CIRIS Engine Continuous Thought Processing Loop ---")
        
        script_cycle_count = 0
        while not self.client.is_closed():
            script_cycle_count += 1
            if max_script_cycles_overall and script_cycle_count > max_script_cycles_overall:
                logger.info(f"Reached max overall script cycles ({max_script_cycles_overall}). Stopping processing loop.")
                break
            
            if not self.thought_manager or not self.coordinator:
                logger.error("ThoughtManager or Coordinator not initialized. Waiting...")
                await asyncio.sleep(5)
                continue

            current_processing_round = script_cycle_count
            self.thought_manager.current_round_number = current_processing_round
            
            logger.debug(f"Processing Loop Cycle {script_cycle_count}: Populating queue for round {current_processing_round}.")
            self.thought_manager.populate_round_queue(round_number=current_processing_round, max_items=1)

            if not self.thought_manager.current_round_queue:
                await asyncio.sleep(self.discord_config.queue_check_interval_seconds if hasattr(self.discord_config, 'queue_check_interval_seconds') else 5)
                continue

            queued_thought_item = self.thought_manager.get_next_thought_from_queue()
            if not queued_thought_item:
                await asyncio.sleep(1)
                continue

            logger.info(f"Cycle {script_cycle_count}: Processing thought ID {queued_thought_item.thought_id} - Content: {str(queued_thought_item.content)[:60]}...")
            
            original_discord_message_obj: Optional[discord.Message] = None
            if queued_thought_item.initial_context and "discord_message_obj" in queued_thought_item.initial_context:
                original_discord_message_obj = queued_thought_item.initial_context["discord_message_obj"]
            
            if not original_discord_message_obj:
                logger.error(f"Thought {queued_thought_item.thought_id} is missing 'discord_message_obj' in its context. Cannot process for Discord actions.")
                self.thought_manager.update_thought_status(
                    queued_thought_item.thought_id, ThoughtStatus(status="failed"), current_processing_round, 
                    {"error": "Missing discord_message_obj in context"}
                )
                continue

            final_action_result: Optional[ActionSelectionPDMAResult] = None
            try:
                final_action_result = await self.coordinator.process_thought(
                    thought_item=queued_thought_item,
                    current_platform_context=queued_thought_item.initial_context
                )
            except InstructorRetryException as e_instr:
                error_detail = e_instr.errors() if hasattr(e_instr, 'errors') else str(e_instr)
                logger.error(f"CRITICAL (Cycle {script_cycle_count}): InstructorRetryException for thought {queued_thought_item.thought_id}: {error_detail}", exc_info=True)
                self.thought_manager.update_thought_status(
                    queued_thought_item.thought_id, ThoughtStatus(status="failed"), script_cycle_count, {"error": f"InstructorRetryException: {error_detail}"}
                )
            except ValidationError as e_pyd:
                error_detail = e_pyd.errors() if hasattr(e_pyd, 'errors') else str(e_pyd)
                logger.error(f"CRITICAL (Cycle {script_cycle_count}): Pydantic ValidationError for thought {queued_thought_item.thought_id}: {error_detail}", exc_info=True)
                self.thought_manager.update_thought_status(
                    queued_thought_item.thought_id, ThoughtStatus(status="failed"), script_cycle_count, {"error": f"Pydantic ValidationError: {error_detail}"}
                )
            except Exception as e_gen:
                logger.error(f"CRITICAL (Cycle {script_cycle_count}): General Exception for thought {queued_thought_item.thought_id}: {e_gen}", exc_info=True)
                self.thought_manager.update_thought_status(
                    queued_thought_item.thought_id, ThoughtStatus(status="failed"), script_cycle_count, {"error": f"General Exception: {e_gen}"}
                )

            if final_action_result is None: 
                logger.info(f"Cycle {script_cycle_count}: Thought {queued_thought_item.thought_id} was re-queued for Ponder by coordinator.")
                db_thought_after_ponder = self.thought_manager.get_thought_by_id(queued_thought_item.thought_id)
                if db_thought_after_ponder:
                    logger.info(f"DB state for {queued_thought_item.thought_id} AFTER Ponder in cycle {script_cycle_count}: "
                                 f"Status='{db_thought_after_ponder.status.status}', "
                                 f"PonderCount={db_thought_after_ponder.ponder_count}, "
                                 f"PonderNotes='{db_thought_after_ponder.ponder_notes}'")
            elif final_action_result:
                logger.info(f"--- Cycle {script_cycle_count}: Final Action Result for thought {queued_thought_item.thought_id} ---")
                logger.info(f"Selected Action: {final_action_result.selected_handler_action.value}")
                logger.info(f"Action Parameters: {final_action_result.action_parameters}")

                action_type = final_action_result.selected_handler_action
                action_params = final_action_result.action_parameters if final_action_result.action_parameters else {}

                if action_type == HandlerActionType.SPEAK:
                    logger.info(f"Dispatching SPEAK action for thought {queued_thought_item.thought_id} to Discord handler.")
                    await handle_discord_speak(
                        self.client,
                        original_discord_message_obj,
                        action_params.get("message_content", "No message content specified.")
                    )
                elif action_type == HandlerActionType.DEFER_TO_WA:
                    logger.info(f"Dispatching DEFER_TO_WA action for thought {queued_thought_item.thought_id} to Discord handler.")
                    await handle_discord_deferral(
                        self.client,
                        original_discord_message_obj,
                        action_params, 
                        str(self.discord_config.deferral_channel_id) # Ensure it's a string
                    )
                elif action_type == HandlerActionType.PONDER: 
                    logger.error(f"Cycle {script_cycle_count}: Thought {queued_thought_item.thought_id} - PONDER action returned by coordinator, but re-queue failed. Treating as DEFER_TO_WA.")
                    await handle_discord_deferral(
                        self.client, 
                        original_discord_message_obj, 
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
                    logger.info(f"Cycle {script_cycle_count}: Thought {queued_thought_item.thought_id} REJECTED. Rationale: {action_params.get('reason', 'N/A')}")
                elif action_type == HandlerActionType.NO_ACTION:
                    logger.info(f"Cycle {script_cycle_count}: Thought {queued_thought_item.thought_id} resulted in NO_ACTION. Rationale: {action_params.get('reason', 'N/A')}")

                if action_type != HandlerActionType.PONDER: # Ponder re-queue handled by WC, Ponder failure handled above.
                    self.thought_manager.update_thought_status(
                        thought_id=queued_thought_item.thought_id,
                        new_status=ThoughtStatus(status="processed"),
                        round_processed=current_processing_round,
                        processing_result=final_action_result.model_dump()
                    )
            await asyncio.sleep(0.2)

        logger.info(f"--- CIRIS Engine Continuous Thought Processing Loop has ended ---")

    def run(self):
        """Starts the Discord bot."""
        if not self.discord_config.token:
            logger.critical("Discord bot token not found. Cannot start.")
            return
        
        logger.info("Starting Discord client...")
        try:
            self.client.run(self.discord_config.token)
        except discord.LoginFailure:
            logger.error("Discord login failed. Check your DISCORD_BOT_TOKEN.")
        except Exception as e:
            logger.critical(f"An error occurred while running the Discord client: {e}", exc_info=True)

if __name__ == "__main__":
    setup_basic_logging(level=logging.INFO)
    
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("Error: OPENAI_API_KEY environment variable not set.")
    elif not os.environ.get("DISCORD_BOT_TOKEN"):
        logger.error("Error: DISCORD_BOT_TOKEN environment variable not set.")
    else:
        bot_engine = CIRISDiscordEngineBot()
        bot_engine.run()
