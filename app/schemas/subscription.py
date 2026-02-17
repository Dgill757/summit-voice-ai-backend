from __future__ import annotations

from pydantic import BaseModel


class SubscriptionSchema(BaseModel):
    id: str
    plan: str
    status: str
