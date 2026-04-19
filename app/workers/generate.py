from app.adapters.inbound.amqp.handlers.generate import GenerateHandler
from app.container import Container
from app.workers import worker


@worker(
    name="generate",
    queue="generate.request",
    exchange="communication.exchange",
    routing_key="generate.request",
)
def create_generate_handler(container: Container) -> GenerateHandler:
    return GenerateHandler(publisher=container.publisher)
