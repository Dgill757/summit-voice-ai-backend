from __future__ import annotations

from pydantic import BaseModel, Field


class BuilderGenerateRequest(BaseModel):
    description: str = Field(min_length=10, max_length=4000)


class BuilderGenerateResponse(BaseModel):
    code: str
    filename: str
    suggested_config: dict


class BuilderDeployRequest(BaseModel):
    filename: str
    code: str
    config: dict = Field(default_factory=dict)


class BuilderDeployResponse(BaseModel):
    success: bool
    filepath: str
    module: str
    validation_errors: list[str] = Field(default_factory=list)
