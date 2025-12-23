"""
API Version 1 Router

This module combines all v1 API endpoints into a single router.
"""

from fastapi import APIRouter

from .endpoints import chat, search, admin, health

# Create the main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["chat"]
)

api_router.include_router(
    search.router,
    prefix="/search", 
    tags=["search"]
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"]
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)