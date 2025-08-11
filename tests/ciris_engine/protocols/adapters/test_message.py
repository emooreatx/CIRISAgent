"""Tests for Message Protocol."""

from typing import Optional

import pytest

from ciris_engine.protocols.adapters.message import MessageDict, MessageProtocol


class TestMessageProtocol:
    """Test suite for MessageProtocol."""

    def test_message_dict_implements_protocol(self):
        """Test that MessageDict implements MessageProtocol."""
        assert isinstance(MessageDict(), MessageProtocol)

    def test_message_dict_content_property(self):
        """Test content property access."""
        msg = MessageDict({"content": "Hello, world!"})
        assert msg.content == "Hello, world!"

        empty_msg = MessageDict()
        assert empty_msg.content is None

    def test_message_dict_user_id_property(self):
        """Test user_id property access."""
        msg = MessageDict({"user_id": "user123"})
        assert msg.user_id == "user123"

        empty_msg = MessageDict()
        assert empty_msg.user_id is None

    def test_message_dict_author_id_property(self):
        """Test author_id property access."""
        msg = MessageDict({"author_id": "author456"})
        assert msg.author_id == "author456"

        empty_msg = MessageDict()
        assert empty_msg.author_id is None

    def test_message_dict_channel_id_property(self):
        """Test channel_id property access."""
        msg = MessageDict({"channel_id": "channel789"})
        assert msg.channel_id == "channel789"

        empty_msg = MessageDict()
        assert empty_msg.channel_id is None

    def test_message_dict_message_id_property(self):
        """Test message_id property access."""
        msg = MessageDict({"message_id": "msg123"})
        assert msg.message_id == "msg123"

        empty_msg = MessageDict()
        assert empty_msg.message_id is None

    def test_message_dict_id_property(self):
        """Test id property access."""
        msg = MessageDict({"id": "id456"})
        assert msg.id == "id456"

        empty_msg = MessageDict()
        assert empty_msg.id is None

    def test_message_dict_is_dm_property(self):
        """Test is_dm property access."""
        dm_msg = MessageDict({"is_dm": True})
        assert dm_msg.is_dm is True

        channel_msg = MessageDict({"is_dm": False})
        assert channel_msg.is_dm is False

        empty_msg = MessageDict()
        assert empty_msg.is_dm is None

    def test_message_dict_all_properties(self):
        """Test MessageDict with all properties set."""
        data = {
            "content": "Test message",
            "user_id": "user1",
            "author_id": "author1",
            "channel_id": "channel1",
            "message_id": "msg1",
            "id": "id1",
            "is_dm": False,
        }
        msg = MessageDict(data)

        assert msg.content == "Test message"
        assert msg.user_id == "user1"
        assert msg.author_id == "author1"
        assert msg.channel_id == "channel1"
        assert msg.message_id == "msg1"
        assert msg.id == "id1"
        assert msg.is_dm is False

    def test_message_dict_inherits_dict_behavior(self):
        """Test that MessageDict still behaves like a dict."""
        msg = MessageDict({"content": "Hello", "extra": "data"})

        # Dict operations should work
        assert msg["content"] == "Hello"
        assert msg.get("extra") == "data"
        assert "content" in msg
        assert len(msg) == 2

        # Can update like a dict
        msg["new_field"] = "new_value"
        assert msg["new_field"] == "new_value"

    def test_message_dict_with_discord_style_message(self):
        """Test MessageDict with Discord-style message structure."""
        discord_msg = MessageDict(
            {
                "content": "Discord message",
                "author_id": "discord_user",  # Discord uses author_id
                "channel_id": "discord_channel",
                "id": "discord_msg_id",  # Discord uses id for message ID
            }
        )

        assert discord_msg.content == "Discord message"
        assert discord_msg.author_id == "discord_user"
        assert discord_msg.channel_id == "discord_channel"
        assert discord_msg.id == "discord_msg_id"
        assert discord_msg.user_id is None  # Not set in Discord style
        assert discord_msg.message_id is None  # Not set in Discord style

    def test_message_dict_with_api_style_message(self):
        """Test MessageDict with API-style message structure."""
        api_msg = MessageDict(
            {
                "content": "API message",
                "user_id": "api_user",  # API uses user_id
                "channel_id": "api_channel",
                "message_id": "api_msg_id",  # API uses message_id
            }
        )

        assert api_msg.content == "API message"
        assert api_msg.user_id == "api_user"
        assert api_msg.channel_id == "api_channel"
        assert api_msg.message_id == "api_msg_id"
        assert api_msg.author_id is None  # Not set in API style
        assert api_msg.id is None  # Not set in API style

    def test_custom_message_implementation(self):
        """Test that custom classes can implement MessageProtocol."""

        class CustomMessage:
            """Custom message implementation."""

            def __init__(self, content: str, user: str):
                self._content = content
                self._user = user

            @property
            def content(self) -> Optional[str]:
                return self._content

            @property
            def user_id(self) -> Optional[str]:
                return self._user

            @property
            def author_id(self) -> Optional[str]:
                return None

            @property
            def channel_id(self) -> Optional[str]:
                return "default_channel"

            @property
            def message_id(self) -> Optional[str]:
                return "custom_msg"

            @property
            def id(self) -> Optional[str]:
                return None

            @property
            def is_dm(self) -> Optional[bool]:
                return False

        msg = CustomMessage("Custom content", "custom_user")

        # Should be recognized as MessageProtocol
        assert isinstance(msg, MessageProtocol)
        assert msg.content == "Custom content"
        assert msg.user_id == "custom_user"
        assert msg.channel_id == "default_channel"

    def test_message_dict_empty_initialization(self):
        """Test MessageDict with no initial data."""
        msg = MessageDict()

        # All properties should return None
        assert msg.content is None
        assert msg.user_id is None
        assert msg.author_id is None
        assert msg.channel_id is None
        assert msg.message_id is None
        assert msg.id is None
        assert msg.is_dm is None

        # Should still work as empty dict
        assert len(msg) == 0
        assert dict(msg) == {}

    def test_message_dict_partial_data(self):
        """Test MessageDict with only some fields set."""
        msg = MessageDict({"content": "Partial", "is_dm": True})

        assert msg.content == "Partial"
        assert msg.is_dm is True

        # Other fields should be None
        assert msg.user_id is None
        assert msg.author_id is None
        assert msg.channel_id is None
        assert msg.message_id is None
        assert msg.id is None

    def test_message_dict_type_coercion(self):
        """Test that MessageDict doesn't coerce types."""
        msg = MessageDict({"content": 123, "is_dm": "true"})  # Wrong type  # String instead of bool

        # Should return values as-is without type coercion
        assert msg.content == 123
        assert msg.is_dm == "true"
