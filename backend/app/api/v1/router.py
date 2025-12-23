"""
API v1 Router

Main router that includes all v1 API endpoints for the SAGE RAG API.
"""

from fastapi import APIRouter

from .endpoints import chat, search, admin, health

# Create main API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)

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