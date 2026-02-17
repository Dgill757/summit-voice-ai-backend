from __future__ import annotations

from pydantic import BaseModel


class WorkflowSchema(BaseModel):
    id: str
    name: str
    is_active: bool
