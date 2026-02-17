from __future__ import annotations

from pydantic import BaseModel


class LeadSchema(BaseModel):
    id: str
    company_name: str
    status: str
    lead_score: int
