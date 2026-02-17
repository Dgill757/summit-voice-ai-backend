from __future__ import annotations

from pydantic import BaseModel


class AgentSchema(BaseModel):
    id: int
    name: str
    enabled: bool
