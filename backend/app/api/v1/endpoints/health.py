"""
Health check endpoints for the SAGE RAG API

Basic health monitoring and status endpoints.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends #type: ignore
from datetime import datetime

from app.models import HealthStatus
from app.services.rag_manager import RAGManager
from app.api.dependencies import get_rag_manager

router = APIRouter()
logger = logging.getLogger("api.health")


@router.get(
    "/",
    response_model=HealthStatus,
    summary="Basic health check",
    description="Check if the service is running and responding"
)
async def health_check() -> HealthStatus:
    """
    Basic health check endpoint
    
    Returns the basic health status of the service.
    """
    # Provide the full HealthStatus fields expected by the Pydantic model.
    # timestamp: current UTC time
    # services: individual component readiness status (keep empty or populate as available)
    # uptime: seconds since service start (fallback to 0.0 if not tracked)
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(),
        services={"api": True},
        uptime=0.0,
    )


@router.get(
    "/ready",
    summary="Readiness check",
    description="Check if the service is ready to handle requests"
)
async def readiness_check(
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> Dict[str, Any]:
    """
    Readiness check endpoint
    
    Checks if all components are initialized and ready to handle requests.
    """
    try:
        health_data = await rag_manager.health_check()
        
        is_ready = (
            health_data.get("initialized", False) and
            health_data.get("database_accessible", False)
        )

        return {
            "status": "healthy" if is_ready else "unhealthy",
            "service": "SAGE RAG API",
            "version": "1.0.0",
            "timestamp": datetime.now(),
            "components": health_data
        }
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "service": "SAGE RAG API",
            "version": "1.0.0",
            "error": str(e)
        }


@router.get(
    "/live",
    summary="Liveness check",
    description="Check if the service is alive and functioning"
)
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check endpoint
    
    Simple check to verify the service is alive.
    """
    return {
        "status": "alive",
        "service": "SAGE RAG API",
        "version": "1.0.0"
    }