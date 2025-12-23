"""
Brief: FastAPI app entrypoint with portable, USB-friendly initialization.

Starts REST and gRPC services and relies on portable settings to resolve paths.
"""

import sys
import logging
import asyncio
import subprocess
import platform
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Avoid hardcoding or injecting arbitrary sys.path entries; use package imports only.

from app.core.config import Settings
from app.core.logging_config import setup_logging
from app.core.exceptions import RAGException
from app.api.v1.router import api_router
from app.services.rag_manager import RAGManager
from app.grpc_server.server import GRPCServer


def kill_process_on_port(port: int) -> bool:
    """
    Kill any process using the specified port
    
    Args:
        port: Port number to check and clear
        
    Returns:
        True if a process was killed, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        if platform.system() == "Windows":
            # Find process using the port
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if f":{port}" in line and "LISTENING" in line:
                        # Extract PID (last column)
                        parts = line.split()
                        if parts:
                            pid = parts[-1]
                            if pid.isdigit():
                                logger.info(f"Found process {pid} using port {port}, terminating it...")
                                # Kill the process
                                kill_result = subprocess.run(
                                    ["taskkill", "/F", "/PID", pid],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if kill_result.returncode == 0:
                                    logger.info(f"Successfully killed process {pid} on port {port}")
                                    return True
                                else:
                                    logger.warning(f"Failed to kill process {pid}: {kill_result.stderr}")
        else:
            # Unix-like systems (Linux, macOS)
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pid = result.stdout.strip()
                logger.info(f"Found process {pid} using port {port}, terminating it...")
                subprocess.run(["kill", "-9", pid], timeout=5)
                logger.info(f"Successfully killed process {pid} on port {port}")
                return True
                
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while trying to kill process on port {port}")
    except Exception as e:
        logger.error(f"Error killing process on port {port}: {e}")
    
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events
    """
    # Startup
    logger = logging.getLogger(__name__)
    logger.info("Starting SAGE RAG API server...")
    
    try:
        # Initialize RAG Manager
        rag_manager = RAGManager()
        await rag_manager.initialize()
        app.state.rag_manager = rag_manager
        
        # Start gRPC server (optional - will continue if it fails)
        grpc_port = 50051
        try:
            grpc_server = GRPCServer(rag_manager)
            await grpc_server.start()  # Start but don't wait for termination
            app.state.grpc_server = grpc_server
            logger.info("gRPC server started successfully")
        except Exception as grpc_error:
            error_msg = str(grpc_error)
            
            # If port is in use, try to kill the process and retry once
            if "Failed to bind" in error_msg and f":{grpc_port}" in error_msg:
                logger.warning(f"gRPC port {grpc_port} is in use, attempting to free it...")
                
                if kill_process_on_port(grpc_port):
                    # Wait a moment for the port to be released
                    await asyncio.sleep(2)
                    
                    # Retry starting gRPC server
                    try:
                        logger.info(f"Retrying gRPC server startup on port {grpc_port}...")
                        grpc_server = GRPCServer(rag_manager)
                        await grpc_server.start()
                        app.state.grpc_server = grpc_server
                        logger.info("gRPC server started successfully after clearing port")
                    except Exception as retry_error:
                        logger.warning(f"gRPC server failed to start after retry (will continue without it): {retry_error}")
                        app.state.grpc_server = None
                else:
                    logger.warning(f"Could not free port {grpc_port}, continuing without gRPC server")
                    app.state.grpc_server = None
            else:
                logger.warning(f"gRPC server failed to start (will continue without it): {grpc_error}")
                app.state.grpc_server = None
        
        logger.info("SAGE RAG API server started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down SAGE RAG API server...")
    
    try:
        # Stop gRPC server
        if hasattr(app.state, 'grpc_server'):
            await app.state.grpc_server.stop()
        
        # Cleanup RAG Manager
        if hasattr(app.state, 'rag_manager'):
            await app.state.rag_manager.cleanup()
            
        logger.info("SAGE RAG API server shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application
    """
    settings = Settings()
    
    # Setup logging
    setup_logging(settings.log_level)
    
    # Create FastAPI app with lifespan
    app = FastAPI(
        title="SAGE RAG API",
        description="Educational Chatbot RAG Backend",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """Add security headers to all responses"""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
    
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all incoming requests"""
        logger = logging.getLogger("api.requests")
        
        # Extract user info from headers (set by Go backend)
        user_id = request.headers.get("X-User-ID", "anonymous")
        username = request.headers.get("X-Username", "anonymous")
        user_role = request.headers.get("X-User-Role", "anonymous")
        
        logger.info(
            f"{request.method} {request.url.path} | "
            f"User: {username} ({user_id}) | "
            f"Role: {user_role} | "
            f"IP: {request.client.host}"
        )
        
        response = await call_next(request)
        
        logger.info(
            f"Response: {response.status_code} | "
            f"User: {username} | "
            f"Path: {request.url.path}"
        )
        
        return response
    
    # Exception handlers
    @app.exception_handler(RAGException)
    async def rag_exception_handler(request: Request, exc: RAGException):
        """Handle custom RAG exceptions"""
        logger = logging.getLogger(__name__)
        logger.error(f"RAG Exception: {exc.detail} | Code: {exc.error_code}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_code": exc.error_code,
                "type": "RAGException"
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors"""
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "error_code": "VALIDATION_ERROR",
                "details": exc.errors()
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "error_code": "HTTP_ERROR"
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions"""
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
                "details": str(exc) if settings.debug else "An unexpected error occurred"
            }
        )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "service": "SAGE RAG API",
            "version": "1.0.0"
        }
    
    # Include API router
    app.include_router(api_router, prefix="/api/v1")
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    settings = Settings()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True
    )