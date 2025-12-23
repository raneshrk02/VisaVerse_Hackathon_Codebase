"""
gRPC Server Implementation for SAGE RAG API

This module implements the gRPC server that allows the Go backend to communicate
with the Python RAG service for chat and search operations.
"""

import asyncio
import logging
import grpc #type: ignore
import subprocess
import platform
from concurrent import futures
from typing import Optional

# Import generated gRPC code
from . import chat_service_pb2
from . import chat_service_pb2_grpc

from app.services.rag_manager import RAGManager
from app.models import (
    ChatRequest as APIChatRequest,
    SearchRequest as APISearchRequest,
    UserContext,
    UserRole,
    ChatMessage
)
from app.core.config import settings
from app.core.exceptions import RAGException, AuthorizationError


class ChatServiceServicer(chat_service_pb2_grpc.ChatServiceServicer):
    """
    gRPC service implementation for chat operations
    """
    
    def __init__(self, rag_manager: RAGManager):
        self.rag_manager = rag_manager
        self.logger = logging.getLogger("grpc.chat_service")
    
    async def ProcessChat(self, request, context):
        """
        Process a chat request via gRPC
        
        Args:
            request: gRPC ChatRequest
            context: gRPC context
            
        Returns:
            gRPC ChatResponse
        """
        try:
            self.logger.info(f"gRPC chat request from {request.user_context.username}")
            
            # Convert gRPC request to API request
            user_context = self._convert_user_context(request.user_context)
            
            # Convert conversation history
            conversation_history = []
            for msg in request.conversation_history:
                conversation_history.append(
                    ChatMessage(
                        role=msg.role,
                        content=msg.content,
                        timestamp=msg.timestamp
                    )
                )
            
            api_request = APIChatRequest(
                message=request.message,
                class_num=request.class_num if request.HasField('class_num') else None,
                conversation_history=conversation_history,
                include_sources=request.include_sources,
                max_sources=request.max_sources
            )
            
            # Process the chat request
            response = await self.rag_manager.process_chat(api_request, user_context)
            
            # Convert to gRPC response
            grpc_response = self._convert_chat_response(response)
            
            self.logger.info(f"gRPC chat response sent to {user_context.username}")
            return grpc_response
            
        except RAGException as e:
            self.logger.error(f"RAG error in gRPC chat: {e.detail}")
            return self._create_error_chat_response(str(e.detail))
        except Exception as e:
            self.logger.error(f"Unexpected error in gRPC chat: {e}", exc_info=True)
            return self._create_error_chat_response("Internal server error")
    
    async def SearchDocuments(self, request, context):
        """
        Search documents via gRPC
        
        Args:
            request: gRPC SearchRequest
            context: gRPC context
            
        Returns:
            gRPC SearchResponse
        """
        try:
            self.logger.info(f"gRPC search request from {request.user_context.username}")
            
            # Convert gRPC request to API request
            user_context = self._convert_user_context(request.user_context)
            
            api_request = APISearchRequest(
                query=request.query,
                class_num=request.class_num if request.HasField('class_num') else None,
                top_k=request.top_k,
                similarity_threshold=request.similarity_threshold
            )
            
            # Process the search request
            response = await self.rag_manager.search_documents(api_request, user_context)
            
            # Convert to gRPC response
            grpc_response = self._convert_search_response(response)
            
            self.logger.info(f"gRPC search response sent to {user_context.username}")
            return grpc_response
            
        except RAGException as e:
            self.logger.error(f"RAG error in gRPC search: {e.detail}")
            return self._create_error_search_response(str(e.detail))
        except Exception as e:
            self.logger.error(f"Unexpected error in gRPC search: {e}")
            return self._create_error_search_response("Internal server error")
    
    async def GetHealth(self, request, context):
        """
        Get health status via gRPC
        
        Args:
            request: gRPC HealthRequest
            context: gRPC context
            
        Returns:
            gRPC HealthResponse
        """
        try:
            health_data = await self.rag_manager.health_check()
            
            return {
                'status': health_data.get('status', 'unknown'),
                'service': 'SAGE RAG API',
                'version': '1.0.0',
                'initialized': health_data.get('initialized', False),
                'database_accessible': health_data.get('database_accessible', False),
                'uptime': int(health_data.get('uptime', 0)),
                'error_message': ''
            }
            
        except Exception as e:
            self.logger.error(f"Error in gRPC health check: {e}")
            return {
                'status': 'unhealthy',
                'service': 'SAGE RAG API',
                'version': '1.0.0',
                'initialized': False,
                'database_accessible': False,
                'uptime': 0,
                'error_message': str(e)
            }
    
    async def GetStats(self, request, context):
        """
        Get service statistics via gRPC (admin only)
        
        Args:
            request: gRPC StatsRequest
            context: gRPC context
            
        Returns:
            gRPC StatsResponse
        """
        try:
            user_context = self._convert_user_context(request.user_context)
            
            # Check admin permissions
            if user_context.role not in [UserRole.ADMIN, UserRole.ROOT_ADMIN]:
                raise AuthorizationError("Admin privileges required")
            
            stats = await self.rag_manager.get_service_stats()
            
            # Convert to gRPC response
            return self._convert_stats_response(stats)
            
        except AuthorizationError as e:
            self.logger.warning(f"Authorization error in gRPC stats: {e}")
            return self._create_error_stats_response("Insufficient permissions")
        except Exception as e:
            self.logger.error(f"Error in gRPC stats: {e}")
            return self._create_error_stats_response(str(e))
    
    def _convert_user_context(self, grpc_user_context) -> UserContext:
        """Convert gRPC UserContext to API UserContext"""
        return UserContext(
            user_id=grpc_user_context.user_id,
            username=grpc_user_context.username,
            email=grpc_user_context.email or None,
            role=UserRole(grpc_user_context.role),
            school_id=grpc_user_context.school_id or None
        )
    
    def _convert_chat_response(self, api_response):
        """Convert API ChatResponse to gRPC ChatResponse"""
        # Convert source documents
        sources = []
        for source in api_response.sources:
            grpc_source = chat_service_pb2.SourceDocument(
                content=source.content,
                rank=int(source.rank or 0)
            )
            
            # Handle metadata as map field
            if hasattr(source, 'metadata') and source.metadata:
                for key, value in source.metadata.items():
                    grpc_source.metadata[str(key)] = str(value)
            
            # Handle optional source_class
            if source.source_class is not None:
                grpc_source.source_class = int(source.source_class)
                
            sources.append(grpc_source)
        
        grpc_response = chat_service_pb2.ChatResponse(
            answer=str(api_response.answer),
            sources=sources,
            confidence=float(api_response.confidence),
            processing_time=float(api_response.processing_time),
            success=True,
            error_message=''
        )
        
        # Handle metadata as map field
        if hasattr(api_response, 'metadata') and api_response.metadata:
            for key, value in api_response.metadata.items():
                grpc_response.metadata[str(key)] = str(value)
        
        # Handle optional conversation_id
        if api_response.conversation_id:
            grpc_response.conversation_id = str(api_response.conversation_id)
            
        return grpc_response
    
    def _convert_search_response(self, api_response):
        """Convert API QueryResponse to gRPC SearchResponse"""
        # Convert source documents
        sources = []
        for source in api_response.results:
            grpc_source = chat_service_pb2.SourceDocument(
                content=source.content,
                rank=source.rank or 0
            )
            
            # Handle metadata as map field
            if hasattr(source, 'metadata') and source.metadata:
                for key, value in source.metadata.items():
                    grpc_source.metadata[str(key)] = str(value)
            
            if source.source_class is not None:
                grpc_source.source_class = source.source_class
            sources.append(grpc_source)
        
        return chat_service_pb2.SearchResponse(
            results=sources,
            total_results=api_response.total_results,
            processing_time=api_response.processing_time,
            query_metadata=api_response.query_metadata,
            success=True,
            error_message=''
        )
    
    def _convert_stats_response(self, api_stats):
        """Convert API StatsResponse to gRPC StatsResponse"""
        # Convert database status
        collections = []
        for collection in api_stats.database_status.collections:
            collections.append({
                'name': collection.name,
                'document_count': collection.document_count,
                'metadata': collection.metadata
            })
        
        database_status = {
            'collections': collections,
            'total_documents': api_stats.database_status.total_documents,
            'status': api_stats.database_status.status
        }
        
        return {
            'total_queries': api_stats.total_queries,
            'cache_hit_rate': api_stats.cache_hit_rate,
            'average_processing_time': api_stats.average_processing_time,
            'database_status': database_status,
            'uptime': api_stats.uptime,
            'success': True,
            'error_message': ''
        }
    
    def _create_error_chat_response(self, error_message: str):
        """Create error ChatResponse"""
        return chat_service_pb2.ChatResponse(
            answer='',
            sources=[],
            confidence=0.0,
            processing_time=0.0,
            metadata={},
            success=False,
            error_message=error_message
        )
    
    def _create_error_search_response(self, error_message: str):
        """Create error SearchResponse"""
        return chat_service_pb2.SearchResponse(
            results=[],
            total_results=0,
            processing_time=0.0,
            query_metadata={},
            success=False,
            error_message=error_message
        )
    
    def _create_error_stats_response(self, error_message: str):
        """Create error StatsResponse"""
        return {
            'total_queries': 0,
            'cache_hit_rate': 0.0,
            'average_processing_time': 0.0,
            'database_status': {
                'collections': [],
                'total_documents': 0,
                'status': 'unknown'
            },
            'uptime': 0.0,
            'success': False,
            'error_message': error_message
        }


class GRPCServer:
    """
    gRPC server wrapper for managing the server lifecycle
    """
    
    def __init__(self, rag_manager: RAGManager):
        self.rag_manager = rag_manager
        self.server: Optional[grpc.aio.Server] = None
        self.logger = logging.getLogger("grpc.server")
    
    def _kill_process_on_port(self, port: int) -> bool:
        """
        Kill any process using the specified port
        
        Args:
            port: Port number to check and clear
            
        Returns:
            True if a process was killed, False otherwise
        """
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
                                    self.logger.info(f"Found process {pid} using port {port}, terminating it...")
                                    # Kill the process
                                    kill_result = subprocess.run(
                                        ["taskkill", "/F", "/PID", pid],
                                        capture_output=True,
                                        text=True,
                                        timeout=5
                                    )
                                    if kill_result.returncode == 0:
                                        self.logger.info(f"Successfully killed process {pid} on port {port}")
                                        return True
                                    else:
                                        self.logger.warning(f"Failed to kill process {pid}: {kill_result.stderr}")
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
                    self.logger.info(f"Found process {pid} using port {port}, terminating it...")
                    subprocess.run(["kill", "-9", pid], timeout=5)
                    self.logger.info(f"Successfully killed process {pid} on port {port}")
                    return True
                    
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout while trying to kill process on port {port}")
        except Exception as e:
            self.logger.error(f"Error killing process on port {port}: {e}")
        
        return False
    
    async def start(self):
        """Start the gRPC server"""
        try:
            # First, try to clear the port if it's in use
            self._kill_process_on_port(settings.grpc_port)
            
            # Wait a moment for the port to be released
            await asyncio.sleep(2)
            
            self.logger.info(f"Starting gRPC server on {settings.grpc_host}:{settings.grpc_port}")
            
            # Create server
            self.server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
            
            # Add service
            chat_servicer = ChatServiceServicer(self.rag_manager)
            
            # Register the service
            chat_service_pb2_grpc.add_ChatServiceServicer_to_server(chat_servicer, self.server)
            
            # Add insecure port
            listen_addr = f'{settings.grpc_host}:{settings.grpc_port}'
            self.server.add_insecure_port(listen_addr)
            
            # Start server
            await self.server.start()
            
            self.logger.info(f"gRPC server started on {listen_addr}")
            
            # Don't wait for termination here - let it run in background
            
        except Exception as e:
            self.logger.error(f"Failed to start gRPC server: {e}")
            raise
    
    async def stop(self):
        """Stop the gRPC server"""
        if self.server:
            self.logger.info("Stopping gRPC server...")
            await self.server.stop(grace=5)
            self.logger.info("gRPC server stopped")


# Note: To generate the actual gRPC Python code, run:
# python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. chat_service.proto