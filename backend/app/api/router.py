"""Root API router.

Every feature router is mounted here and nowhere else, so the full surface of the
API can be read off a single file.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
