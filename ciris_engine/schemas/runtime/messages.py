"""
Message schemas for CIRIS Trinity Architecture.

Typed message structures for all communication types.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class IncomingMessage(BaseModel):
    """Schema for incoming messages from various sources."""

    message_id: str = Field(..., description="Unique message identifier")
    author_id: str = Field(..., description="Message author ID")
    author_name: str = Field(..., description="Message author name")
    content: str = Field(..., description="Message content")
    destination_id: Optional[str] = Field(default=None, alias="channel_id")
    reference_message_id: Optional[str] = Field(None, description="ID of message being replied to")
    timestamp: Optional[str] = Field(None, description="Message timestamp")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @property
    def channel_id(self) -> Optional[str]:
        """Backward compatibility alias for destination_id."""
        return self.destination_id


class DiscordMessage(IncomingMessage):
    """Incoming message specific to the Discord platform."""

    is_bot: bool = Field(default=False, description="Whether author is a bot")
    is_dm: bool = Field(default=False, description="Whether this is a DM")
    raw_message: Optional[Any] = Field(default=None, exclude=True)  # Discord.py message object

    def __init__(self, **data: Any) -> None:
        if "destination_id" not in data and "channel_id" in data:
            data["destination_id"] = data.get("channel_id")
        super().__init__(**data)


class FetchedMessage(BaseModel):
    """Message returned by CommunicationService.fetch_messages."""

    message_id: Optional[str] = Field(default=None, alias="id")
    content: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    timestamp: Optional[str] = None
    is_bot: Optional[bool] = False

    model_config = ConfigDict(populate_by_name=True, extra="allow")


__all__ = [
    "IncomingMessage",
    "DiscordMessage",
    "FetchedMessage",
]
