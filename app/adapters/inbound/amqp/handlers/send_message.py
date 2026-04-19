import structlog

from app.adapters.outbound.amqp.publisher import RabbitMQPublisher
from app.domain.entities.message import OutboundChannelMessage
from app.ports.inbound.message_handler import MessageHandler

logger = structlog.get_logger(__name__)


class SendMessageHandler(MessageHandler):
    """
    Handles outbound messages to send via communication channels.
    This is what communication does - it sends messages, it doesn't "generate" anything.
    """

    def __init__(self, publisher: RabbitMQPublisher) -> None:
        self._publisher = publisher

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
        except Exception as exc:
            log.error("send_message.failed", error=str(exc))
            raise

    async def _send_to_channel(self, message: OutboundChannelMessage) -> None:
        """
        Send message to the appropriate communication channel.
        TODO: Implement actual channel sending logic here.
        """
        logger.info(
            "channel.sending",
            channel_type=message.channel.channel_type,
            recipient=message.channel.recipient_id,
            content_preview=message.content[:50],
        )
        # TODO: Route to appropriate channel adapter (WhatsApp, Email, etc.)
