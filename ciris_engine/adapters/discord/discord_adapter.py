import discord
import logging
from ciris_engine.adapters.discord.discord_event_queue import DiscordEventQueue
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage

logger = logging.getLogger(__name__)

class DiscordAdapter:
    """
    Minimal DiscordAdapter for CIRISAgent. Wraps the event queue and provides send_output.
    """
    def __init__(self, token: str, message_queue: DiscordEventQueue):
        self.token = token
        self.message_queue = message_queue
        self.client = None  # Placeholder for actual Discord client if needed

    async def send_output(self, channel_id: str, content: str):
        if not self.client:
            logger.error("Discord client is not initialized.")
            return
        # Wait for the client to be ready before sending
        if hasattr(self.client, 'wait_until_ready'):
            await self.client.wait_until_ready()
        try:
            channel = self.client.get_channel(int(channel_id))
            if channel is None:
                channel = await self.client.fetch_channel(int(channel_id))
            if channel:
                await channel.send(content)
            else:
                logger.error(f"Could not find Discord channel with ID {channel_id}")
        except Exception as e:
            logger.exception(f"Failed to send message to Discord channel {channel_id}: {e}")

    async def on_message(self, message):
        # Only process messages from users (not bots)
        if message.author.bot:
            return
        # Build IncomingMessage object
        incoming = IncomingMessage(
            message_id=str(message.id),
            content=message.content,
            author_id=str(message.author.id),
            author_name=message.author.display_name,
            channel_id=str(message.channel.id),
            _raw_message=message
        )
        await self.message_queue.enqueue(incoming)

    def attach_to_client(self, client):
        # Attach the on_message event to the Discord client
        @client.event
        async def on_message(message):
            await self.on_message(message)

    async def start(self):
        pass

    async def stop(self):
        pass
