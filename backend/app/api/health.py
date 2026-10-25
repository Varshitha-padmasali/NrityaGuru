from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.database import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str
    gemini_configured: bool
    database_configured: bool


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    # Reports only whether secrets are set, never their values.
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        gemini_configured=settings.gemini_configured,
        database_configured=settings.database_configured,
    )


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness: proves the database is reachable. Database problems become a generic 503."""
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
