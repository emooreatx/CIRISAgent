import pytest
from unittest.mock import MagicMock, patch
from ciris_engine.services.discord_service import DiscordService, DiscordConfig

@patch("ciris_engine.services.discord_service.DiscordEventQueue")
@patch("ciris_engine.services.discord_service.ToolRegistry")
@patch("ciris_engine.services.discord_service.register_discord_tools")
@patch("ciris_engine.services.discord_service.discord.Client")
def test_discord_service_init(mock_client, mock_register, mock_toolreg, mock_eventq):
    dispatcher = MagicMock()
    config = DiscordConfig(bot_token_env_var="X", deferral_channel_id_env_var="Y", wa_user_id_env_var="Z", monitored_channel_id_env_var="W")
    with patch("os.getenv", return_value="123456789"):
        service = DiscordService(dispatcher, config=config)
    assert service.action_dispatcher is dispatcher
    assert service.config is config
