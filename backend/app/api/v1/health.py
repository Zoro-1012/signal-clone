"""Liveness and readiness endpoints.

Kept outside the versioned business API: a hosting platform's health probe should
not have to care which API version is current.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, Any]:
    """Confirm the process is up. Deliberately does no I/O."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/health/ready", summary="Readiness probe")
async def readiness(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Confirm the process can actually serve traffic, i.e. the database answers."""
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
