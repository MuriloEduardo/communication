import asyncio
from functools import partial

import boto3
import structlog

from app.ports.outbound.media_storage import MediaStoragePort

logger = structlog.get_logger(__name__)


class S3MediaStorage(MediaStoragePort):
    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        presign_expires: int = 3600,
        aws_access_key_id: str = "",
        aws_secret_access_key: str = "",
    ) -> None:
        self._bucket = bucket
        self._presign_expires = presign_expires
        self._client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=aws_access_key_id or None,
            aws_secret_access_key=aws_secret_access_key or None,
        )

    async def upload_and_sign(self, data: bytes, key: str, content_type: str) -> str:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            ),
        )
        url: str = await loop.run_in_executor(
            None,
            partial(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=self._presign_expires,
            ),
        )
        logger.info("s3.uploaded", key=key, bucket=self._bucket)
        return url
