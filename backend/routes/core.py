from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import text

from backend.crud.core import HealthResponse
from backend.db.core import db_session

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health(db_session: AsyncSession = Depends(db_session)) -> HealthResponse:
    await db_session.exec(text("SELECT 1"))

    return HealthResponse(status="ok", database=True)
