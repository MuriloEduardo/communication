"""
Meta WhatsApp Business Cloud API client.
Handles sending text messages and read receipts.
"""

import asyncio

import structlog
import httpx

logger = structlog.get_logger(__name__)

META_API_BASE = "https://graph.facebook.com/v22.0"


class MetaWhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str) -> None:
        self.phone_number_id = phone_number_id
        self._client = httpx.AsyncClient(
            base_url=f"{META_API_BASE}/{phone_number_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        self._media_client = httpx.AsyncClient(
            base_url=META_API_BASE,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )

    async def send_text(self, to: str, body: str) -> dict:
        response = await self._client.post(
            "/messages",
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": body},
            },
        )
        if not response.is_success:
            logger.error(
                "whatsapp.api_error",
                status=response.status_code,
                body=response.text,
                to=to,
            )
            response.raise_for_status()
        data = response.json()
        msg_id = (data.get("messages") or [{}])[0].get("id")
        logger.info("whatsapp.sent", to=to, message_id=msg_id)
        return data

    async def mark_as_read(self, message_id: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        logger.info(
            "whatsapp.mark_as_read.start", message_id=message_id, payload=payload
        )
        try:
            resp = await self._client.post("/messages", json=payload)
            logger.info(
                "whatsapp.mark_as_read.response",
                message_id=message_id,
                status=resp.status_code,
                body=resp.text,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error(
                "whatsapp.mark_as_read.error",
                message_id=message_id,
                error=str(exc),
            )

    async def send_typing(self, to: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": " "},
            "typing_indicator": {"type": "text"},
        }
        logger.info("whatsapp.send_typing.start", to=to, payload=payload)
        for attempt in range(2):
            try:
                resp = await self._client.post("/messages", json=payload)
                logger.info(
                    "whatsapp.send_typing.response",
                    to=to,
                    attempt=attempt + 1,
                    status=resp.status_code,
                    body=resp.text,
                )
                if resp.is_success:
                    logger.info("whatsapp.send_typing.success", to=to)
                    return
            except Exception as exc:
                logger.error(
                    "whatsapp.send_typing.exception",
                    to=to,
                    attempt=attempt + 1,
                    error=str(exc),
                )
            if attempt == 0:
                logger.info("whatsapp.send_typing.retry", to=to)
                await asyncio.sleep(1.0)
        logger.error("whatsapp.send_typing.all_attempts_failed", to=to)

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """Download media from Meta. Returns (bytes, mime_type)."""
        info = (await self._media_client.get(f"/{media_id}")).raise_for_status().json()
        data = (await self._media_client.get(info["url"])).raise_for_status()
        return data.content, info.get("mime_type", "application/octet-stream")

    async def close(self) -> None:
        await self._client.aclose()
        await self._media_client.aclose()
