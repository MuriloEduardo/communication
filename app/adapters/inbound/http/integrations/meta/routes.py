import asyncio
import json
from datetime import date
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
MEDIA_TYPES = {"image", "video", "audio", "document", "sticker"}

_MIME_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/3gpp": ".3gpp",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/aac": ".aac",
    "audio/opus": ".opus",
    "application/pdf": ".pdf",
}


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


async def _upload_media(
    whatsapp, media_storage, media_id: str, mime_type: str, phone_number_id: str
) -> str:
    """Download media from Meta and upload to S3. Returns pre-signed URL."""
    today = date.today()
    ext = _MIME_EXT.get(mime_type, "")
    key = f"whatsapp/{phone_number_id}/{today.year}/{today.month:02d}/{today.day:02d}/{media_id}{ext}"
    data, _ = await whatsapp.download_media(media_id)
    return await media_storage.upload_and_sign(data, key, mime_type)


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
    media_storage = container.media_storage

    has_text_messages = False
    media_urls: dict[str, str] = {}  # message_id → pre-signed S3 URL

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

                # ── Media download + S3 upload ──
                if msg.type in MEDIA_TYPES and whatsapp and media_storage and msg.id:
                    media = getattr(msg, msg.type, None)
                    if media:
                        try:
                            url = await _upload_media(
                                whatsapp,
                                media_storage,
                                media.id,
                                media.mime_type,
                                phone_number_id or "unknown",
                            )
                            media_urls[msg.id] = url
                        except Exception:
                            logger.warning(
                                "media.upload_failed", msg_id=msg.id, media_id=media.id
                            )

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
        payload_dict = json.loads(payload.model_dump_json())
        if media_urls:
            payload_dict["_media_urls"] = media_urls
        await publisher.publish(
            message=json.dumps(payload_dict).encode(),
            routing_key=ROUTING_KEY,
            exchange_name=EXCHANGE,
        )

    logger.info("meta.webhook.published", entries=len(payload.entry))
    return {"status": "received"}
