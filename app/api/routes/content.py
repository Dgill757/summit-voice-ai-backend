"""
Content API Routes
Manage content calendar
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime

from app.database import get_db
from app.models import ContentCalendar
from pydantic import BaseModel
from app.services.image_generator import ImageGenerator
from app.core.security import get_current_user

router = APIRouter()


class ContentCreate(BaseModel):
    title: str
    content_type: str | None = None
    platform: str | None = None
    content_body: str | None = None
    media_url: str | None = None
    status: str | None = "review"


@router.get("/")
async def list_content(
    status: str = None,
    platform: str = None,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    List content calendar items
    """
    query = db.query(ContentCalendar)

    if status:
        query = query.filter(ContentCalendar.status == status)
    if platform:
        query = query.filter(ContentCalendar.platform == platform)

    content = query.order_by(ContentCalendar.scheduled_date.desc()).all()

    return [
        {
            "id": str(c.id),
            "title": c.title,
            "content_type": c.content_type,
            "platform": c.platform,
            "status": c.status,
            "scheduled_date": c.scheduled_date.isoformat() if c.scheduled_date else None,
            "published_at": c.published_at.isoformat() if c.published_at else None
        }
        for c in content
    ]


@router.get("/{content_id}")
async def get_content(content_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get content details
    """
    content = db.query(ContentCalendar).filter(ContentCalendar.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return {
        "id": str(content.id),
        "title": content.title,
        "content_type": content.content_type,
        "platform": content.platform,
        "content_body": content.content_body,
        "media_url": content.media_url,
        "status": content.status,
        "scheduled_date": content.scheduled_date.isoformat() if content.scheduled_date else None,
        "scheduled_time": content.scheduled_time.isoformat() if content.scheduled_time else None,
        "published_at": content.published_at.isoformat() if content.published_at else None,
        "target_audience": content.target_audience,
        "keywords": content.keywords,
        "performance_goal": content.performance_goal
    }


@router.post("/")
async def create_content(
    payload: ContentCreate,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    row = ContentCalendar(
        title=payload.title,
        content_type=payload.content_type,
        platform=payload.platform,
        content_body=payload.content_body,
        media_url=payload.media_url,
        status=payload.status or "review",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "title": row.title,
        "content_type": row.content_type,
        "platform": row.platform,
        "status": row.status,
    }


@router.post("/{content_id}/generate-image")
async def generate_content_image(
    content_id: str,
    model: str = "auto",
    style: str = "photorealistic",
    aspect_ratio: str = "1:1",
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Generate AI image for content"""

    content = db.query(ContentCalendar).filter(ContentCalendar.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Generate image description from content
    generator = ImageGenerator()

    # Use first 100 chars of content as prompt
    prompt = (content.content_body or "")[:100]

    try:
        result = await generator.generate_image(
            prompt=prompt,
            model=model,
            style=style,
            aspect_ratio=aspect_ratio
        )

        # Store image URL in content
        content.media_url = result["url"]

        meta = content.meta or {}
        meta["image_generation"] = {
            "model": result["model_used"],
            "prompt": result["enhanced_prompt"],
            "generated_at": datetime.utcnow().isoformat()
        }
        content.meta = meta

        db.commit()

        return {
            "success": True,
            "image_url": result["url"],
            "model_used": result["model_used"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")
