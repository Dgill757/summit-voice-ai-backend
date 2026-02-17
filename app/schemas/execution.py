from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class ExecutionSchema(BaseModel):
    id: str
    agent_id: int
    status: str
    message: str | None = None
    created_at: datetime | None = None
