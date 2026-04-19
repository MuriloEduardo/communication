import structlog

from app.adapters.inbound.amqp.consumer import RabbitMQConsumer
from app.adapters.outbound.amqp.publisher import RabbitMQPublisher
from app.adapters.outbound.http.meta_whatsapp import MetaWhatsAppClient
from app.infrastructure.config.settings import Settings
from app.infrastructure.messaging.rabbitmq_connection import RabbitMQConnection
from app.ports.inbound.message_handler import MessageHandler

logger = structlog.get_logger(__name__)


class Container:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._connection: RabbitMQConnection | None = None
        self._publisher: RabbitMQPublisher | None = None
        self._whatsapp_client: MetaWhatsAppClient | None = None

    @property
    def connection(self) -> RabbitMQConnection:
        if self._connection is None:
            self._connection = RabbitMQConnection(self.settings)
        return self._connection

    @property
    def publisher(self) -> RabbitMQPublisher:
        if self._publisher is None:
            self._publisher = RabbitMQPublisher(self.connection)
        return self._publisher

    @property
    def whatsapp_client(self) -> MetaWhatsAppClient | None:
        if self._whatsapp_client is None and self.settings.meta_access_token:
            self._whatsapp_client = MetaWhatsAppClient(
                access_token=self.settings.meta_access_token,
                phone_number_id=self.settings.whatsapp_phone_number_id,
            )
        return self._whatsapp_client

    def consumer(self, handler: MessageHandler) -> RabbitMQConsumer:
        return RabbitMQConsumer(self.connection, handler)

    async def shutdown(self) -> None:
        if self._whatsapp_client:
            await self._whatsapp_client.close()
        if self._connection:
            await self._connection.close()
        logger.info("container.shutdown")
