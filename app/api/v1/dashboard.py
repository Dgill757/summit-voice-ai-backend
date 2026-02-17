from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.metrics_service import get_kpis
from app.services.integration_service import integration_status

router = APIRouter()


@router.get('/')
async def dashboard_data(db: Session = Depends(get_db)):
    return {
        'kpis': get_kpis(db),
        'integrations': integration_status()['integrations'],
    }
