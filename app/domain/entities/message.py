"""
Communication service entities.
Communication only deals with channel messages (inbound/outbound).
It doesn't know about "generation" - just receives and sends messages.
"""

import sys
from pathlib import Path

# Add parent directory to path to import shared_schemas
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
from shared_schemas import (
    ChannelMetadata,
    InboundChannelMessage,
    OutboundChannelMessage,
)

__all__ = [
    "ChannelMetadata",
    "InboundChannelMessage",
    "OutboundChannelMessage",
]
