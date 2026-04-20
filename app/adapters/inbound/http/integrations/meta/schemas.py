from __future__ import annotations

from pydantic import BaseModel, Field


# ── Nested schemas matching Meta WhatsApp Cloud API webhook payload ──


class MetaContactProfile(BaseModel):
    model_config = {"extra": "allow"}
    name: str | None = None


class MetaContact(BaseModel):
    model_config = {"extra": "allow"}
    profile: MetaContactProfile | None = None
    wa_id: str | None = None
    user_id: str | None = None


class MetaTextBody(BaseModel):
    body: str


class MetaReaction(BaseModel):
    message_id: str
    emoji: str


class MetaMessageContext(BaseModel):
    model_config = {"extra": "allow"}
    from_: str | None = Field(None, alias="from")
    id: str | None = None  # noqa: A003


class MetaMessage(BaseModel):
    model_config = {"extra": "allow"}
    id: str  # noqa: A003
    type: str = "text"
    timestamp: str | None = None
    from_: str | None = Field(None, alias="from")
    from_user_id: str | None = None
    text: MetaTextBody | None = None
    reaction: MetaReaction | None = None
    context: MetaMessageContext | None = None


class MetaStatusPricing(BaseModel):
    model_config = {"extra": "allow"}
    billable: bool | None = None
    pricing_model: str | None = None
    category: str | None = None
    type: str | None = None


class MetaStatus(BaseModel):
    model_config = {"extra": "allow"}
    id: str  # noqa: A003
    status: str
    timestamp: str | None = None
    recipient_id: str | None = None
    pricing: MetaStatusPricing | None = None


class MetaMetadata(BaseModel):
    model_config = {"extra": "allow"}
    display_phone_number: str | None = None
    phone_number_id: str | None = None


class MetaChangeValue(BaseModel):
    model_config = {"extra": "allow"}
    messaging_product: str = "whatsapp"
    metadata: MetaMetadata | None = None
    contacts: list[MetaContact] = []
    messages: list[MetaMessage] = []
    statuses: list[MetaStatus] = []


class MetaChange(BaseModel):
    model_config = {"extra": "allow"}
    value: MetaChangeValue
    field: str = "messages"


class MetaEntry(BaseModel):
    model_config = {"extra": "allow"}
    id: str  # noqa: A003
    changes: list[MetaChange] = []


class MetaWebhookPayload(BaseModel):
    """
    Root schema for Meta WhatsApp Cloud API webhook payloads.

    Examples
    --------
    Inbound text message::

        {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "111377161860817",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550280506",
                            "phone_number_id": "109628212037229"
                        },
                        "contacts": [{
                            "profile": {"name": "Murilo Eduardo"},
                            "wa_id": "555174019092",
                            "user_id": "BR.4808878556007727"
                        }],
                        "messages": [{
                            "from": "555174019092",
                            "from_user_id": "BR.4808878556007727",
                            "id": "wamid.HBgMNTU1MTc0MDE5MDkyFQIAEhg...",
                            "timestamp": "1776641274",
                            "text": {"body": "Ok"},
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

    Status update::

        {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "111377161860817",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550280506",
                            "phone_number_id": "109628212037229"
                        },
                        "contacts": [{
                            "wa_id": "555174019092",
                            "user_id": "BR.4808878556007727"
                        }],
                        "statuses": [{
                            "id": "wamid.HBgMNTU1MTc0MDE5MDkyFQIAERgS...",
                            "status": "sent",
                            "timestamp": "1776641287",
                            "recipient_id": "555174019092",
                            "pricing": {
                                "billable": false,
                                "pricing_model": "PMP",
                                "category": "service",
                                "type": "free_customer_service"
                            }
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
    """

    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "examples": [
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "111377161860817",
                            "changes": [
                                {
                                    "value": {
                                        "messaging_product": "whatsapp",
                                        "metadata": {
                                            "display_phone_number": "15550280506",
                                            "phone_number_id": "109628212037229",
                                        },
                                        "contacts": [
                                            {
                                                "profile": {"name": "Murilo Eduardo"},
                                                "wa_id": "555174019092",
                                                "user_id": "BR.4808878556007727",
                                            }
                                        ],
                                        "messages": [
                                            {
                                                "from": "555174019092",
                                                "from_user_id": "BR.4808878556007727",
                                                "id": "wamid.HBgMNTU1MTc0MDE5MDkyFQIAEhgWM0VCMDIxMzQzMEYwN0IyRDk4ODZEMAA=",
                                                "timestamp": "1776641895",
                                                "text": {"body": "oizinhuuu"},
                                                "type": "text",
                                            }
                                        ],
                                    },
                                    "field": "messages",
                                }
                            ],
                        }
                    ],
                },
                {
                    "object": "whatsapp_business_account",
                    "entry": [
                        {
                            "id": "111377161860817",
                            "changes": [
                                {
                                    "value": {
                                        "messaging_product": "whatsapp",
                                        "metadata": {
                                            "display_phone_number": "15550280506",
                                            "phone_number_id": "109628212037229",
                                        },
                                        "contacts": [
                                            {
                                                "wa_id": "555174019092",
                                                "user_id": "BR.4808878556007727",
                                            }
                                        ],
                                        "statuses": [
                                            {
                                                "id": "wamid.HBgMNTU1MTc0MDE5MDkyFQIAERgSQzQxREU3Q0QyNkQwNkM2RTg1AA==",
                                                "status": "sent",
                                                "timestamp": "1776641287",
                                                "recipient_id": "555174019092",
                                                "recipient_user_id": "BR.4808878556007727",
                                                "pricing": {
                                                    "billable": False,
                                                    "pricing_model": "PMP",
                                                    "category": "service",
                                                    "type": "free_customer_service",
                                                },
                                            }
                                        ],
                                    },
                                    "field": "messages",
                                }
                            ],
                        }
                    ],
                },
            ]
        },
    }

    object: str
    entry: list[MetaEntry] = []
