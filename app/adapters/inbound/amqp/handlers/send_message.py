import asyncio

import structlog

from app.adapters.outbound.http.meta_whatsapp import MetaWhatsAppClient
from app.adapters.outbound.postgres import ChannelEventRepository
from app.domain.entities.message import ChannelType, OutboundChannelMessage
from app.ports.inbound.message_handler import MessageHandler

logger = structlog.get_logger(__name__)


class SendMessageHandler(MessageHandler):
    """
    Handles outbound messages to send via communication channels.
    Routes to the appropriate channel adapter (WhatsApp, etc.).
    """

    def __init__(
        self,
        whatsapp_client: MetaWhatsAppClient | None = None,
        events: ChannelEventRepository | None = None,
    ) -> None:
        self._whatsapp = whatsapp_client
        self._events = events

    async def handle(
        self, message: bytes, routing_key: str, headers: dict | None = None
    ) -> None:
        if not message:
            logger.warning("send_message.empty_message", routing_key=routing_key)
            return

        outbound = OutboundChannelMessage.model_validate_json(message)
        log = logger.bind(
            message_id=outbound.message_id,
            channel=outbound.channel.channel_type,
        )
        log.info("send_message.received")

        try:
            await self._send_to_channel(outbound)
            log.info("send_message.sent")
            if self._events:
                sender_id = outbound.channel.sender_id or (
                    self._whatsapp.phone_number_id if self._whatsapp else None
                )
                asyncio.create_task(
                    self._events.record(
                        direction="outbound",
                        channel=outbound.channel.channel_type,
                        event_type="sent",
                        sender_id=sender_id,
                        recipient_id=outbound.channel.recipient_id,
                        message_id=outbound.message_id,
                        content=outbound.content,
                    )
                )
        except Exception as exc:
            log.error("send_message.failed", error=str(exc))
            if self._events:
                sender_id = outbound.channel.sender_id or (
                    self._whatsapp.phone_number_id if self._whatsapp else None
                )
                asyncio.create_task(
                    self._events.record(
                        direction="outbound",
                        channel=outbound.channel.channel_type,
                        event_type="failed",
                        sender_id=sender_id,
                        recipient_id=outbound.channel.recipient_id,
                        message_id=outbound.message_id,
                        metadata={"error": str(exc)},
                    )
                )
            raise

    async def _send_to_channel(self, message: OutboundChannelMessage) -> None:
        if message.channel.channel_type == ChannelType.WHATSAPP:
            if not self._whatsapp:
                logger.warning("whatsapp.not_configured")
                return
            inbound_msg_id = message.metadata.get("inbound_message_id")
            if inbound_msg_id:
                await self._whatsapp.mark_as_read(inbound_msg_id, typing=True)
            await self._whatsapp.send_text(
                to=message.channel.recipient_id or "",
                body=message.content,
            )
        else:
            logger.warning(
                "channel.unsupported",
                channel_type=message.channel.channel_type,
            )
