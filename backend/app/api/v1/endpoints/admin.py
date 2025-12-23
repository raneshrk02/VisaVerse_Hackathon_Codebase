"""
Admin endpoints for the SAGE RAG API

Handles administrative functions, system monitoring, and management operations.
"""

import logging
import time
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException #type: ignore

from app.models import (
    UserContext,
    StatsResponse,
    DatabaseStatus
)
from app.services.rag_manager import RAGManager
from app.core.exceptions import RAGException, AuthorizationError
from app.api.dependencies import get_rag_manager, get_user_context, require_admin

router = APIRouter()
logger = logging.getLogger("api.admin")


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get system statistics",
    description="Get comprehensive system statistics and performance metrics",
    dependencies=[Depends(require_admin)]
)
async def get_system_stats(
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> StatsResponse:
    """
    Get system statistics and performance metrics
    
    Requires admin or root admin role.
    """
    try:
        logger.info(f"Stats request from admin {user_context.username}")
        
        stats = await rag_manager.get_service_stats()
        
        return stats
        
    except RAGException as e:
        logger.error(f"RAG error in stats endpoint: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Error getting system stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system statistics")


@router.get(
    "/database/status",
    response_model=DatabaseStatus,
    summary="Get database status",
    description="Get detailed database status and collection information",
    dependencies=[Depends(require_admin)]
)
async def get_database_status(
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> DatabaseStatus:
    """
    Get database status and collection information
    
    Requires admin or root admin role.
    """
    try:
        logger.info(f"Database status request from admin {user_context.username}")
        
        status = await rag_manager.get_database_status()
        
        return status
        
    except RAGException as e:
        logger.error(f"RAG error in database status endpoint: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Error getting database status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get database status")


@router.get(
    "/health/detailed",
    summary="Get detailed health status",
    description="Get comprehensive health check information for all components",
    dependencies=[Depends(require_admin)]
)
async def get_detailed_health(
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> Dict[str, Any]:
    """
    Get detailed health status for all system components
    
    Requires admin or root admin role.
    """
    try:
        logger.info(f"Detailed health check from admin {user_context.username}")
        
        # Get RAG manager health
        rag_health = await rag_manager.health_check()
        
        # Get database status
        try:
            db_status = await rag_manager.get_database_status()
            database_health = {
                "status": "healthy" if db_status.status == "healthy" else "unhealthy",
                "total_collections": len(db_status.collections),
                "total_documents": db_status.total_documents,
                "collections": [
                    {
                        "name": col.name,
                        "document_count": col.document_count
                    }
                    for col in db_status.collections
                ]
            }
        except Exception as e:
            database_health = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Get service stats
        try:
            stats = await rag_manager.get_service_stats()
            performance_health = {
                "status": "healthy",
                "total_queries": stats.total_queries,
                "cache_hit_rate": stats.cache_hit_rate,
                "average_processing_time": stats.average_processing_time,
                "uptime": stats.uptime
            }
        except Exception as e:
            performance_health = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Overall health determination
        overall_status = "healthy"
        if (rag_health.get("status") != "healthy" or 
            database_health.get("status") != "healthy" or
            performance_health.get("status") != "healthy"):
            overall_status = "unhealthy"
        
        return {
            "overall_status": overall_status,
            "components": {
                "rag_manager": rag_health,
                "database": database_health,
                "performance": performance_health
            },
            "timestamp": "2025-01-01T00:00:00Z"  # Would use actual timestamp
        }
        
    except Exception as e:
        logger.error(f"Error in detailed health check: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


@router.post(
    "/cache/clear",
    summary="Clear system cache",
    description="Clear the RAG system cache to free memory",
    dependencies=[Depends(require_admin)]
)
async def clear_cache(
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> Dict[str, Any]:
    """
    Clear the RAG system cache
    
    Requires admin or root admin role.
    """
    try:
        logger.info(f"Cache clear request from admin {user_context.username}")
        
        # Clear cache using RAG manager
        result = rag_manager.clear_cache()
        
        if result["status"] == "success":
            return {
                "status": "success",
                "message": result["message"],
                "items_cleared": result.get("items_cleared", 0),
                "cleared_by": user_context.username,
                "timestamp": time.time()
            }
        else:
            raise HTTPException(status_code=500, detail=result["message"])
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")




@router.get(
    "/metrics",
    summary="Get system metrics",
    description="Get Prometheus-style metrics for monitoring",
    dependencies=[Depends(require_admin)]
)
async def get_metrics(
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> Dict[str, Any]:
    """
    Get system metrics in a format suitable for monitoring
    
    Requires admin or root admin role.
    """
    try:
        logger.info(f"Metrics request from admin {user_context.username}")
        
        stats = await rag_manager.get_service_stats()
        
        return {
            "metrics": {
                "rag_total_queries": stats.total_queries,
                "rag_cache_hit_rate": stats.cache_hit_rate,
                "rag_average_processing_time": stats.average_processing_time,
                "rag_uptime_seconds": stats.uptime,
                "database_total_documents": stats.database_status.total_documents,
                "database_total_collections": len(stats.database_status.collections)
            },
            "timestamp": "2025-01-01T00:00:00Z"  # Would use actual timestamp
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get metrics")