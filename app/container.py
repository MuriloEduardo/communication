import structlog

from app.adapters.inbound.amqp.consumer import RabbitMQConsumer
from app.adapters.outbound.amqp.publisher import RabbitMQPublisher
from app.adapters.outbound.http.meta_whatsapp import MetaWhatsAppClient
from app.adapters.outbound.postgres import ChannelEventRepository
from app.adapters.outbound.s3.media_storage import S3MediaStorage
from app.infrastructure.config.settings import Settings
from app.infrastructure.database import PostgresConnection
from app.infrastructure.messaging.rabbitmq_connection import RabbitMQConnection
from app.domain.services.meta_webhook_processor import MetaWebhookProcessor
from app.ports.inbound.message_handler import MessageHandler
from app.ports.outbound.media_storage import MediaStoragePort

logger = structlog.get_logger(__name__)


class Container:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._connection: RabbitMQConnection | None = None
        self._publisher: RabbitMQPublisher | None = None
        self._whatsapp_client: MetaWhatsAppClient | None = None
        self._database: PostgresConnection | None = None
        self._events: ChannelEventRepository | None = None
        self._media_storage: MediaStoragePort | None = None
        self._webhook_processor: MetaWebhookProcessor | None = None

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

    @property
    def database(self) -> PostgresConnection:
        if self._database is None:
            self._database = PostgresConnection(self.settings)
        return self._database

    @property
    def events(self) -> ChannelEventRepository:
        if self._events is None:
            self._events = ChannelEventRepository(self.database)
        return self._events

    @property
    def media_storage(self) -> MediaStoragePort | None:
        if self._media_storage is None and self.settings.aws_s3_bucket:
            self._media_storage = S3MediaStorage(
                bucket=self.settings.aws_s3_bucket,
                region=self.settings.aws_s3_region,
                presign_expires=self.settings.aws_s3_presign_expires,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            )
        return self._media_storage

    @property
    def webhook_processor(self) -> MetaWebhookProcessor:
        if self._webhook_processor is None:
            self._webhook_processor = MetaWebhookProcessor(
                publisher=self.publisher,
                whatsapp_client=self.whatsapp_client,
                events=self.events,
                media_storage=self.media_storage,
            )
        return self._webhook_processor

    def consumer(self, handler: MessageHandler) -> RabbitMQConsumer:
        return RabbitMQConsumer(self.connection, handler)

    async def shutdown(self) -> None:
        if self._whatsapp_client:
            await self._whatsapp_client.close()
        if self._database:
            await self._database.close()
        if self._connection:
            await self._connection.close()
        logger.info("container.shutdown")
