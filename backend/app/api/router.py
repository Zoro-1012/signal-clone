"""Root API router.

Every feature router is mounted here and nowhere else, so the full surface of the
API can be read off a single file.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, contacts, conversations, health, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(contacts.router)
api_router.include_router(conversations.router)
