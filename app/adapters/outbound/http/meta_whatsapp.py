"""
Meta WhatsApp Business Cloud API client.
Handles sending text messages and read receipts.
"""

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

    async def mark_as_read(self, message_id: str, typing: bool = False) -> None:
        payload: dict = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        if typing:
            payload["typing_indicator"] = {"type": "text"}
        try:
            resp = await self._client.post("/messages", json=payload)
            resp.raise_for_status()
            logger.debug("whatsapp.marked_read", message_id=message_id, typing=typing)
        except Exception:
            logger.warning("whatsapp.mark_read_failed", message_id=message_id)

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """Download media from Meta. Returns (bytes, mime_type)."""
        info = (await self._media_client.get(f"/{media_id}")).raise_for_status().json()
        data = (await self._media_client.get(info["url"])).raise_for_status()
        return data.content, info.get("mime_type", "application/octet-stream")

    async def close(self) -> None:
        await self._client.aclose()
        await self._media_client.aclose()
