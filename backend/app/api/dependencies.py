"""
Dependency injection for the SAGE RAG API

Provides dependency functions for FastAPI endpoints including
authentication, authorization, and service injection.
"""

import logging
from typing import Optional
from fastapi import Request, HTTPException, Depends

from app.models import UserContext, UserRole
from app.services.rag_manager import RAGManager
from app.core.exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger("api.dependencies")


def get_rag_manager(request: Request) -> RAGManager:
    """
    Get the RAG manager instance from the application state
    
    Args:
        request: FastAPI request object
        
    Returns:
        RAG manager instance
        
    Raises:
        HTTPException: If RAG manager is not available
    """
    rag_manager = getattr(request.app.state, 'rag_manager', None)
    
    if not rag_manager:
        logger.error("RAG manager not found in application state")
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable"
        )
    
    return rag_manager


def get_user_context(request: Request) -> UserContext:
    """
    Extract user context from request headers (set by Go backend)
    
    Args:
        request: FastAPI request object
        
    Returns:
        User context information
        
    Raises:
        HTTPException: If user context is missing or invalid
    """
    try:
        # Extract user information from headers set by Go backend
        user_id = request.headers.get("X-User-ID")
        username = request.headers.get("X-Username")
        email = request.headers.get("X-User-Email")
        role = request.headers.get("X-User-Role")
        school_id = request.headers.get("X-School-ID")
        
        # Validate required headers
        if not user_id or not username or not role:
            logger.warning(
                f"Missing required user headers: "
                f"user_id={bool(user_id)}, username={bool(username)}, role={bool(role)}"
            )
            raise AuthenticationError("User authentication required")
        
        # Validate role
        try:
            user_role = UserRole(role)
        except ValueError:
            logger.error(f"Invalid user role: {role}")
            raise AuthenticationError("Invalid user role")
        
        user_context = UserContext(
            user_id=user_id,
            username=username,
            email=email,
            role=user_role,
            school_id=school_id
        )
        
        logger.debug(f"User context extracted: {username} ({user_role})")
        return user_context
        
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Authentication required")
    except Exception as e:
        logger.error(f"Error extracting user context: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication")


def require_admin(user_context: UserContext = Depends(get_user_context)) -> UserContext:
    """
    Require admin or root admin role
    
    Args:
        user_context: User context from get_user_context
        
    Returns:
        User context if authorized
        
    Raises:
        HTTPException: If user doesn't have required permissions
    """
    if user_context.role not in [UserRole.ADMIN, UserRole.ROOT_ADMIN]:
        logger.warning(
            f"Access denied for user {user_context.username} "
            f"with role {user_context.role}"
        )
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    
    return user_context


def require_root_admin(user_context: UserContext = Depends(get_user_context)) -> UserContext:
    """
    Require root admin role
    
    Args:
        user_context: User context from get_user_context
        
    Returns:
        User context if authorized
        
    Raises:
        HTTPException: If user doesn't have required permissions
    """
    if user_context.role != UserRole.ROOT_ADMIN:
        logger.warning(
            f"Root admin access denied for user {user_context.username} "
            f"with role {user_context.role}"
        )
        raise HTTPException(
            status_code=403,
            detail="Root admin privileges required"
        )
    
    return user_context


def get_optional_user_context(request: Request) -> Optional[UserContext]:
    """
    Get user context if available, otherwise return None
    
    This is useful for endpoints that can work with or without authentication.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User context if available, None otherwise
    """
    try:
        return get_user_context(request)
    except HTTPException:
        return None


def rate_limit_dependency(
    max_requests: int = 100,
    window_seconds: int = 60
):
    """
    Factory function to create rate limiting dependencies
    
    Args:
        max_requests: Maximum requests allowed in the window
        window_seconds: Time window in seconds
        
    Returns:
        Rate limiting dependency function
    """
    # This would implement actual rate limiting logic
    # For now, it's a placeholder
    
    def rate_limit_check(
        request: Request,
        user_context: UserContext = Depends(get_user_context)
    ) -> bool:
        """
        Check rate limit for the user
        
        Args:
            request: FastAPI request object
            user_context: User context
            
        Returns:
            True if within rate limit
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        # Placeholder implementation
        # In a real implementation, you would:
        # 1. Check user's request count in a cache/database
        # 2. Update the count
        # 3. Raise exception if limit exceeded
        
        return True
    
    return rate_limit_check