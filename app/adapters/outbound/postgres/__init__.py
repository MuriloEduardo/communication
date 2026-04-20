import json

import structlog

from app.infrastructure.database import PostgresConnection

logger = structlog.get_logger(__name__)


class ChannelEventRepository:
    def __init__(self, database: PostgresConnection) -> None:
        self._db = database

    async def record(
        self,
        *,
        direction: str,
        channel: str,
        event_type: str,
        sender_id: str | None = None,
        recipient_id: str | None = None,
        message_id: str | None = None,
        content: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        pool = await self._db.get_pool()
        await pool.execute(
            """
            INSERT INTO channel_events
                (direction, channel, event_type, sender_id, recipient_id,
                 message_id, content, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            """,
            direction,
            channel,
            event_type,
            sender_id,
            recipient_id,
            message_id,
            content,
            json.dumps(metadata or {}),
        )
