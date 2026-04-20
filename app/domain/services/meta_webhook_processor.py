"""
Use-case: process an inbound Meta / WhatsApp webhook event.

Receives the raw (dict) payload already parsed from JSON by the HTTP adapter,
applies all business rules (typing indicator, media upload, quoted-message
lookup, event recording, forwarding to workflow) and delegates to the
appropriate outbound ports.
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from app.adapters.outbound.http.meta_whatsapp import MetaWhatsAppClient
    from app.adapters.outbound.postgres import ChannelEventRepository
    from app.ports.outbound.media_storage import MediaStoragePort
    from app.ports.outbound.message_publisher import MessagePublisher

logger = structlog.get_logger(__name__)

_EXCHANGE = "communication.channel.inbound"
_ROUTING_KEY = "channel.inbound.meta"
_MEDIA_TYPES = {"image", "video", "audio", "document", "sticker"}
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


def _extract_content(msg: dict[str, Any]) -> str | None:
    msg_type = msg.get("type", "text")
    if msg_type == "text":
        return (msg.get("text") or {}).get("body")
    if msg_type == "location":
        loc = msg.get("location") or {}
        parts = [f"📍 {loc.get('latitude')},{loc.get('longitude')}"]
        if loc.get("name"):
            parts.append(loc["name"])
        if loc.get("address"):
            parts.append(loc["address"])
        return " — ".join(parts)
    media = msg.get(msg_type) or {}
    return media.get("caption")


def _extract_metadata(msg: dict[str, Any]) -> dict[str, Any]:
    msg_type = msg.get("type", "text")
    meta: dict[str, Any] = {"type": msg_type}

    ctx = msg.get("context") or {}
    if ctx.get("id"):
        meta["reply_to"] = ctx["id"]
        meta["reply_to_from"] = ctx.get("from")

    if msg_type == "reaction":
        reaction = msg.get("reaction") or {}
        meta["emoji"] = reaction.get("emoji")
        meta["reacted_message_id"] = reaction.get("message_id")
        return meta

    if msg_type == "location":
        loc = msg.get("location") or {}
        meta["latitude"] = loc.get("latitude")
        meta["longitude"] = loc.get("longitude")
        if loc.get("name"):
            meta["location_name"] = loc["name"]
        if loc.get("address"):
            meta["location_address"] = loc["address"]
        return meta

    media = msg.get(msg_type) or {}
    if media.get("mime_type"):
        meta["media_id"] = media.get("id")
        meta["mime_type"] = media.get("mime_type")
        if media.get("filename"):
            meta["filename"] = media["filename"]

    return meta


class MetaWebhookProcessor:
    def __init__(
        self,
        publisher: MessagePublisher,
        whatsapp_client: MetaWhatsAppClient | None,
        events: ChannelEventRepository,
        media_storage: MediaStoragePort | None,
    ) -> None:
        self._publisher = publisher
        self._whatsapp = whatsapp_client
        self._events = events
        self._media_storage = media_storage

    async def process(self, payload: dict[str, Any]) -> None:
        has_messages = False
        media_urls: dict[str, str] = {}
        quoted_messages: dict[str, str] = {}

        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                phone_number_id = (value.get("metadata") or {}).get("phone_number_id")

                await self._process_statuses(value.get("statuses", []), phone_number_id)

                for msg in value.get("messages", []):
                    processed = await self._process_message(
                        msg,
                        phone_number_id,
                        media_urls,
                        quoted_messages,
                    )
                    if processed:
                        has_messages = True

        if has_messages:
            if media_urls:
                payload["_media_urls"] = media_urls
            if quoted_messages:
                payload["_quoted_messages"] = quoted_messages
            await self._publisher.publish(
                message=json.dumps(payload).encode(),
                routing_key=_ROUTING_KEY,
                exchange_name=_EXCHANGE,
            )
            logger.info("meta.webhook.forwarded", entries=len(payload.get("entry", [])))

    # ── Private helpers ──────────────────────────────────────────────────────

    async def _process_statuses(
        self,
        statuses: list[dict[str, Any]],
        phone_number_id: str | None,
    ) -> None:
        for status in statuses:
            pricing = status.get("pricing") or {}
            meta: dict[str, Any] = {"type": "status"}
            if pricing:
                meta["pricing"] = pricing
            asyncio.create_task(
                self._events.record(
                    direction="outbound",
                    channel="whatsapp",
                    event_type=status.get("status", "unknown"),
                    sender_id=phone_number_id,
                    recipient_id=status.get("recipient_id"),
                    message_id=status.get("id"),
                    metadata=meta,
                )
            )

    async def _process_message(
        self,
        msg: dict[str, Any],
        phone_number_id: str | None,
        media_urls: dict[str, str],
        quoted_messages: dict[str, str],
    ) -> bool:
        """Returns True if the message should be forwarded to workflow."""
        msg_type = msg.get("type", "text")
        msg_id = msg.get("id")
        sender = msg.get("from")

        if msg_type == "unsupported":
            return False

        if msg_type == "reaction":
            await self._trigger_typing(msg_id)
            asyncio.create_task(
                self._events.record(
                    direction="inbound",
                    channel="whatsapp",
                    event_type="reaction",
                    sender_id=sender,
                    recipient_id=phone_number_id,
                    message_id=msg_id,
                    metadata=_extract_metadata(msg),
                )
            )
            return True

        # Regular message
        await self._trigger_typing(msg_id)
        await self._resolve_quoted_message(msg, quoted_messages)
        await self._upload_media_if_needed(msg, phone_number_id, sender, media_urls)
        asyncio.create_task(
            self._events.record(
                direction="inbound",
                channel="whatsapp",
                event_type="received",
                sender_id=sender,
                recipient_id=phone_number_id,
                message_id=msg_id,
                content=_extract_content(msg),
                metadata=_extract_metadata(msg),
            )
        )
        return True

    async def _trigger_typing(self, msg_id: str | None) -> None:
        if not self._whatsapp or not msg_id:
            return

        async def _read_then_type(wapp=self._whatsapp, mid=msg_id) -> None:
            await asyncio.sleep(random.uniform(0.5, 2.0))
            await wapp.mark_as_read(mid)
            await asyncio.sleep(random.uniform(1.0, 3.0))
            await wapp.send_typing(mid)

        asyncio.create_task(_read_then_type())

    async def _resolve_quoted_message(
        self,
        msg: dict[str, Any],
        quoted_messages: dict[str, str],
    ) -> None:
        ctx = msg.get("context") or {}
        quoted_id = ctx.get("id")
        if not quoted_id or quoted_id in quoted_messages:
            return
        try:
            content = await self._events.get_content_by_message_id(quoted_id)
            if content:
                quoted_messages[quoted_id] = content
        except Exception as exc:
            logger.warning(
                "quoted_message.lookup_failed", quoted_id=quoted_id, error=str(exc)
            )

    async def _upload_media_if_needed(
        self,
        msg: dict[str, Any],
        phone_number_id: str | None,
        sender: str | None,
        media_urls: dict[str, str],
    ) -> None:
        msg_type = msg.get("type", "text")
        msg_id = msg.get("id")
        if (
            msg_type not in _MEDIA_TYPES
            or not self._whatsapp
            or not self._media_storage
            or not msg_id
        ):
            return
        media = msg.get(msg_type) or {}
        media_id = media.get("id")
        mime_type = media.get("mime_type", "application/octet-stream")
        if not media_id:
            return
        try:
            ext = _MIME_EXT.get(mime_type.split(";")[0].strip(), "")
            key = f"whatsapp/{phone_number_id or 'unknown'}/{sender or 'unknown'}/{media_id}{ext}"
            data, _ = await self._whatsapp.download_media(media_id)
            url = await self._media_storage.upload_and_sign(data, key, mime_type)
            media_urls[msg_id] = url
        except Exception as exc:
            logger.warning(
                "media.upload_failed", msg_id=msg_id, media_id=media_id, error=str(exc)
            )
