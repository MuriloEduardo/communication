from app.adapters.inbound.amqp.handlers.send_message import SendMessageHandler
from app.container import Container
from app.workers import worker


@worker(
    name="send_message",
    queue="send.message",
    exchange="communication.exchange",
    routing_key="send.message",
)
def create_send_message_handler(container: Container) -> SendMessageHandler:
    return SendMessageHandler(whatsapp_client=container.whatsapp_client)
