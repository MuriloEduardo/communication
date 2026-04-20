import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, Query, Request, Response

from app.adapters.inbound.http.integrations.meta.schemas import (
    MetaMessage,
    MetaWebhookPayload,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/integrations/meta", tags=["meta"])

EXCHANGE = "communication.channel.inbound"
ROUTING_KEY = "channel.inbound.meta"


def _extract_content(msg: MetaMessage) -> str | None:
    """Extract displayable content from any message type."""
    if msg.type == "text" and msg.text:
        return msg.text.body
    if msg.type == "location" and msg.location:
        parts = [f"📍 {msg.location.latitude},{msg.location.longitude}"]
        if msg.location.name:
            parts.append(msg.location.name)
        if msg.location.address:
            parts.append(msg.location.address)
        return " — ".join(parts)
    # Media types: image, video, audio, document, sticker
    media = getattr(msg, msg.type, None)
    if media and hasattr(media, "caption"):
        return media.caption
    return None


def _extract_metadata(msg: MetaMessage) -> dict[str, Any]:
    """Build rich metadata dict for any message type."""
    meta: dict[str, Any] = {"type": msg.type}

    if msg.context:
        meta["reply_to"] = msg.context.id
        meta["reply_to_from"] = msg.context.from_

    if msg.type == "reaction" and msg.reaction:
        meta["emoji"] = msg.reaction.emoji
        meta["reacted_message_id"] = msg.reaction.message_id
        return meta

    if msg.type == "location" and msg.location:
        meta["latitude"] = msg.location.latitude
        meta["longitude"] = msg.location.longitude
        if msg.location.name:
            meta["location_name"] = msg.location.name
        if msg.location.address:
            meta["location_address"] = msg.location.address
        return meta

    # Media types
    media = getattr(msg, msg.type, None)
    if media and hasattr(media, "mime_type"):
        meta["media_id"] = media.id
        meta["mime_type"] = media.mime_type
        if media.filename:
            meta["filename"] = media.filename

    return meta


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
    events = container.events

    has_text_messages = False
    for entry in payload.entry:
        for change in entry.changes:
            phone_number_id = (
                change.value.metadata.phone_number_id if change.value.metadata else None
            )

            # ── Status updates (sent / delivered / read / failed) ──
            for status in change.value.statuses:
                meta: dict[str, Any] = {"type": "status"}
                if status.pricing:
                    meta["pricing"] = status.pricing.model_dump(exclude_none=True)
                asyncio.create_task(
                    events.record(
                        direction="outbound",
                        channel="whatsapp",
                        event_type=status.status,
                        sender_id=phone_number_id,
                        recipient_id=status.recipient_id,
                        message_id=status.id,
                        metadata=meta,
                    )
                )

            # ── Messages (text, media, reaction, location, etc.) ──
            for msg in change.value.messages:
                if msg.type == "reaction":
                    if whatsapp and msg.id:
                        asyncio.create_task(whatsapp.mark_as_read(msg.id, typing=False))
                    asyncio.create_task(
                        events.record(
                            direction="inbound",
                            channel="whatsapp",
                            event_type="reaction",
                            sender_id=msg.from_,
                            recipient_id=phone_number_id,
                            message_id=msg.id,
                            metadata=_extract_metadata(msg),
                        )
                    )
                    continue

                has_text_messages = True
                if whatsapp and msg.id:
                    asyncio.create_task(whatsapp.mark_as_read(msg.id))

                asyncio.create_task(
                    events.record(
                        direction="inbound",
                        channel="whatsapp",
                        event_type="received",
                        sender_id=msg.from_,
                        recipient_id=phone_number_id,
                        message_id=msg.id,
                        content=_extract_content(msg),
                        metadata=_extract_metadata(msg),
                    )
                )

    if has_text_messages:
        raw = payload.model_dump_json().encode()
        await publisher.publish(
            message=raw,
            routing_key=ROUTING_KEY,
            exchange_name=EXCHANGE,
        )

    logger.info("meta.webhook.published", entries=len(payload.entry))
    return {"status": "received"}
