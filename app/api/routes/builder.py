"""AI Builder API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.builder import (
    BuilderDeployRequest,
    BuilderDeployResponse,
    BuilderGenerateRequest,
    BuilderGenerateResponse,
)
from app.services.ai_builder import AIBuilderService

router = APIRouter()


@router.post('/generate', response_model=BuilderGenerateResponse)
async def generate_builder_code(payload: BuilderGenerateRequest, db: Session = Depends(get_db)) -> BuilderGenerateResponse:
    _ = db
    service = AIBuilderService()
    result = await service.generate_agent_code(payload.description)
    return BuilderGenerateResponse(**result)


@router.post('/deploy', response_model=BuilderDeployResponse)
async def deploy_builder_code(payload: BuilderDeployRequest, db: Session = Depends(get_db)) -> BuilderDeployResponse:
    _ = db
    service = AIBuilderService()
    result = service.deploy_agent_code(payload.filename, payload.code, payload.config)
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result)
    return BuilderDeployResponse(**result)
