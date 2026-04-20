import json

import structlog
from fastapi import APIRouter, Query, Request, Response

from app.adapters.inbound.http.integrations.meta.schemas import MetaWebhookPayload

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/integrations/meta", tags=["meta"])


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
    processor = request.app.state.container.webhook_processor
    payload_dict = json.loads(payload.model_dump_json(by_alias=True))
    await processor.process(payload_dict)
    return {"status": "received"}
