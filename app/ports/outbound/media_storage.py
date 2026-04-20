from abc import ABC, abstractmethod


class MediaStoragePort(ABC):
    @abstractmethod
    async def upload_and_sign(self, data: bytes, key: str, content_type: str) -> str:
        """Upload bytes to storage and return a pre-signed URL."""
