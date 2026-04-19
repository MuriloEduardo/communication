"""
Communication-specific entities.
Only imports what communication service needs.
"""

from pydantic import BaseModel, Field
from typing import Any


class ChannelConfig(BaseModel):
    """Configuration for a specific communication channel."""

    channel_type: str
    enabled: bool = True
    credentials: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)


class MessageDeliveryStatus(BaseModel):
    """Status of message delivery to external channel."""

    message_id: str
    channel_type: str
    status: str  # sent, delivered, failed, read
    delivered_at: str | None = None
    error: str | None = None
    platform_status: dict[str, Any] = Field(default_factory=dict)
