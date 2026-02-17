from __future__ import annotations

from pydantic import BaseModel


class ContentSchema(BaseModel):
    id: str
    title: str
    status: str
    platform: str | None = None
