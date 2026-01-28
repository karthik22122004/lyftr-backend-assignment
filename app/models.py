from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, constr

E164_REGEX = r"^\+[0-9]+$"
ISO_UTC_Z_REGEX = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"


class WebhookMessageIn(BaseModel):
    message_id: constr(min_length=1) = Field(..., description="Unique message id")
    from_msisdn: constr(pattern=E164_REGEX) = Field(..., alias="from")
    to_msisdn: constr(pattern=E164_REGEX) = Field(..., alias="to")
    ts: constr(pattern=ISO_UTC_Z_REGEX) = Field(..., description="ISO-8601 UTC with Z suffix")
    text: Optional[constr(max_length=4096)] = Field(default=None)

    class Config:
        populate_by_name = True


class MessageOut(BaseModel):
    message_id: str
    from_msisdn: str = Field(..., alias="from")
    to_msisdn: str = Field(..., alias="to")
    ts: str
    text: Optional[str] = None
    created_at: str

    class Config:
        populate_by_name = True


class MessagesListOut(BaseModel):
    data: list[MessageOut]
    total: int
    limit: int
    offset: int
