from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.health import HealthResponse
from app.services import health as health_service

router = APIRouter(prefix="/api", tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Banco indisponível"}},
)
def get_health(response: Response, db: Session = Depends(get_db)) -> HealthResponse:
    """Saúde pública (sem autenticação): API respondendo e banco com SELECT 1."""
    result = health_service.get_health(db)
    if result.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
