"""
Custom exceptions for the SAGE RAG API
"""

from typing import Optional


class RAGException(Exception):
    """Base exception for RAG-related errors"""
    
    def __init__(
        self,
        detail: str,
        status_code: int = 500,
        error_code: str = "RAG_ERROR"
    ):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(detail)


class ModelNotFoundError(RAGException):
    """Raised when the LLM model file is not found"""
    
    def __init__(self, model_path: str):
        super().__init__(
            detail=f"Model file not found: {model_path}",
            status_code=503,
            error_code="MODEL_NOT_FOUND"
        )


class ChromaDBError(RAGException):
    """Raised when ChromaDB operations fail"""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=f"ChromaDB error: {detail}",
            status_code=503,
            error_code="CHROMADB_ERROR"
        )


class QueryProcessingError(RAGException):
    """Raised when query processing fails"""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=f"Query processing error: {detail}",
            status_code=422,
            error_code="QUERY_PROCESSING_ERROR"
        )


class AuthenticationError(RAGException):
    """Raised when authentication fails"""
    
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            detail=detail,
            status_code=401,
            error_code="AUTHENTICATION_ERROR"
        )


class AuthorizationError(RAGException):
    """Raised when user lacks required permissions"""
    
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            detail=detail,
            status_code=403,
            error_code="AUTHORIZATION_ERROR"
        )


class ValidationError(RAGException):
    """Raised when input validation fails"""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=f"Validation error: {detail}",
            status_code=422,
            error_code="VALIDATION_ERROR"
        )


class RateLimitError(RAGException):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            detail=detail,
            status_code=429,
            error_code="RATE_LIMIT_ERROR"
        )


class ResourceNotFoundError(RAGException):
    """Raised when a requested resource is not found"""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            detail=f"{resource} not found: {identifier}",
            status_code=404,
            error_code="RESOURCE_NOT_FOUND"
        )


class ServiceUnavailableError(RAGException):
    """Raised when a service is temporarily unavailable"""
    
    def __init__(self, service: str, detail: Optional[str] = None):
        message = f"Service unavailable: {service}"
        if detail:
            message += f" - {detail}"
        
        super().__init__(
            detail=message,
            status_code=503,
            error_code="SERVICE_UNAVAILABLE"
        )