"""
Communication service message entities.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    VOICE = "voice"


class ChannelMetadata(BaseModel):
    model_config = {"extra": "allow"}

    channel_type: ChannelType
    sender_id: str | None = None
    recipient_id: str | None = None
    thread_id: str | None = None
    platform_metadata: dict[str, Any] = Field(default_factory=dict)


class InboundChannelMessage(BaseModel):
    model_config = {"extra": "allow"}

    message_id: str
    content: str
    channel: ChannelMetadata
    received_at: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class OutboundChannelMessage(BaseModel):
    message_id: str
    content: str
    channel: ChannelMetadata
    priority: int = 0
    scheduled_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ChannelType",
    "ChannelMetadata",
    "InboundChannelMessage",
    "OutboundChannelMessage",
]
