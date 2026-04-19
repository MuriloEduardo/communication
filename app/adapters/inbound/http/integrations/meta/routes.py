import asyncio

import structlog
from fastapi import APIRouter, Query, Request, Response

from app.adapters.inbound.http.integrations.meta.schemas import MetaWebhookPayload

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/integrations/meta", tags=["meta"])

EXCHANGE = "communication.channel.inbound"
ROUTING_KEY = "channel.inbound.meta"


@router.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> Response:
    settings = request.app.state.container.settings

    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        logger.info("meta.webhook.verified")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("meta.webhook.verification_failed")
    return Response(status_code=403)


@router.post("/webhook")
async def receive_webhook(request: Request, payload: MetaWebhookPayload) -> dict:
    container = request.app.state.container
    publisher = container.publisher
    whatsapp = container.whatsapp_client

    has_messages = False
    for entry in payload.entry:
        for change in entry.changes:
            for msg in change.value.messages:
                has_messages = True

                # Read receipt + typing indicator (fire-and-forget)
                if whatsapp and msg.id:
                    asyncio.create_task(whatsapp.mark_as_read(msg.id))

    # Only forward to workflow when there are actual user messages
    if has_messages:
        raw = payload.model_dump_json().encode()
        await publisher.publish(
            message=raw,
            routing_key=ROUTING_KEY,
            exchange_name=EXCHANGE,
        )

    logger.info("meta.webhook.published", entries=len(payload.entry))
    return {"status": "received"}
