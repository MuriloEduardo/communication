from pydantic import BaseModel


class MetaWebhookPayload(BaseModel):
    model_config = {"extra": "allow"}

    object: str
    entry: list[dict]
