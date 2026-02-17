from __future__ import annotations

from pydantic import BaseModel


class UserSchema(BaseModel):
    id: str
    email: str
