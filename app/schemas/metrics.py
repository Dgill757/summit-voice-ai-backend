from __future__ import annotations

from pydantic import BaseModel


class MetricsSchema(BaseModel):
    name: str
    value: float
