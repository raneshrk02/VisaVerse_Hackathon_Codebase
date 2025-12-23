"""
Brief: High-level RAG manager that wires portable paths and async pipeline usage.

Ensures paths are updated to USB-aware defaults (data under ../data/ncert_chromadb).
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

# Add local src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import chromadb
from src.config_loader import ConfigLoader, Config
from src.rag_pipeline import RAGPipeline, RAGResponse
from src.db_handler import ChromaDBHandler

from app.core.config import settings
from app.core.exceptions import (
    ModelNotFoundError,
    ChromaDBError,
    QueryProcessingError,
    ServiceUnavailableError
)
from app.models import (
    ChatRequest,
    ChatResponse,
    QueryRequest,
    QueryResponse,
    SourceDocument,
    UserContext,
    DatabaseStatus,
    CollectionInfo,
    StatsResponse
)


class RAGManager:
    """
    High-level RAG service manager that wraps the existing RAG pipeline
    and provides async interfaces for FastAPI integration.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("rag.manager")
        self.rag_pipeline: Optional[RAGPipeline] = None
        self.config: Optional[Config] = None
        self.start_time = time.time()
        self.query_count = 0
        self.cache_hits = 0
        self.total_processing_time = 0.0
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Initialize the RAG pipeline and all components
        """
        try:
            self.logger.info("Initializing RAG Manager...")
            
            # Load configuration from local config.yaml
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
            
            if config_path.exists():
                config_loader = ConfigLoader(str(config_path))
                self.config = config_loader.load_config()
                self.logger.info(f"Loaded configuration from {config_path}")
            else:
                # Use default configuration
                config_loader = ConfigLoader()
                self.config = config_loader.load_config()
                self.logger.warning("Using default configuration")
            
            # Override paths with our settings if needed
            self._update_config_paths()
            
            # Initialize RAG pipeline in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.rag_pipeline = await loop.run_in_executor(
                None, self._initialize_rag_pipeline
            )
            
            self._initialized = True
            self.logger.info("RAG Manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize RAG Manager: {e}")
            raise ServiceUnavailableError("RAG Manager", str(e))
    
    def _update_config_paths(self) -> None:
        """Update configuration paths based on FastAPI settings"""
        # Always prefer resolved absolute path from settings for portability
        self.config.chromadb.persist_directory = str(settings.chromadb_absolute_path)
        
        self.config.llm.model_path = str(settings.model_absolute_path)
        
        # Update RAG settings
        self.config.rag.retrieval.top_k = settings.max_retrieval_results
        self.config.rag.retrieval.similarity_threshold = settings.similarity_threshold
        self.config.rag.generation.max_context_length = settings.max_context_length
    
    def _initialize_rag_pipeline(self) -> RAGPipeline:
        """Initialize RAG pipeline (runs in thread pool)"""
        try:
            # Validate model file exists
            model_path = Path(self.config.llm.model_path)
            if not model_path.exists():
                raise ModelNotFoundError(str(model_path))
            
            # Validate ChromaDB directory (ensure exists; writability is checked in handler)
            chromadb_path = Path(self.config.chromadb.persist_directory)
            if not chromadb_path.exists():
                chromadb_path.mkdir(parents=True, exist_ok=True)
                self.logger.warning(f"Created ChromaDB directory: {chromadb_path}")
            
            # Initialize RAG pipeline
            pipeline = RAGPipeline(self.config)
            self.logger.info("RAG pipeline initialized successfully")
            
            return pipeline
            
        except Exception as e:
            self.logger.error(f"Failed to initialize RAG pipeline: {e}")
            raise
    
    async def process_chat(
        self,
        request: ChatRequest,
        user_context: UserContext
    ) -> ChatResponse:
        """
        Process a chat request and return a response
        
        Args:
            request: Chat request data
            user_context: User context information
            
        Returns:
            Chat response with answer and sources
        """
        if not self._initialized:
            raise ServiceUnavailableError("RAG Manager", "Service not initialized")
        
        start_time = time.time()
        
        try:
            self.logger.info(
                f"Processing chat request from user {user_context.username} "
                f"(ID: {user_context.user_id}): {request.message[:100]}..."
            )
            
            # Process query using RAG pipeline in thread pool
            loop = asyncio.get_event_loop()
            rag_response = await loop.run_in_executor(
                None,
                self._process_query_sync,
                request.message,
                request.class_num,
                request.conversation_history
            )
            
            processing_time = time.time() - start_time
            
            # Update statistics
            self.query_count += 1
            self.total_processing_time += processing_time
            if rag_response.cache_hit:
                self.cache_hits += 1
            
            # Convert to API response format
            response = self._convert_rag_response(rag_response, request, processing_time)
            
            self.logger.info(
                f"Chat request processed successfully in {processing_time:.3f}s "
                f"(cache_hit: {rag_response.cache_hit})"
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing chat request: {e}")
            raise QueryProcessingError(str(e))
    
    async def process_chat_stream(
        self,
        request: ChatRequest,
        user_context: UserContext
    ):
        """
        Process chat request and stream the response word-by-word
        
        Args:
            request: Chat request with question and context
            user_context: User context information
            
        Yields:
            Chunks of the response as they're generated
        """
        if not self._initialized:
            raise ServiceUnavailableError("RAG Manager", "Service not initialized")
        
        start_time = time.time()
        
        try:
            self.logger.info(
                f"Processing streaming chat request from user {user_context.username}: "
                f"{request.message[:100]}..."
            )
            
            # First, retrieve documents (non-streaming part)
            yield {"type": "status", "message": "Retrieving relevant documents..."}
            
            # Get the RAG pipeline streaming generator
            loop = asyncio.get_event_loop()
            
            # Run retrieval in thread pool
            sources_data = await loop.run_in_executor(
                None,
                self._retrieve_sources_sync,
                request.message,
                request.class_num
            )
            
            # Send sources first
            if sources_data and request.include_sources:
                sources = []
                for i, source in enumerate(sources_data[:request.max_sources]):
                    source_doc = {
                        "content": source.get('content', ''),
                        "metadata": source.get('metadata', {}),
                        "source_class": source.get('source_class'),
                        "rank": i + 1
                    }
                    sources.append(source_doc)
                
                yield {"type": "sources", "sources": sources}
            
            yield {"type": "status", "message": "Generating answer..."}
            
            # Stream the answer generation
            async for chunk in self._generate_answer_stream(
                request.message,
                sources_data,
                request.conversation_history
            ):
                yield chunk
            
            processing_time = time.time() - start_time
            
            # Update statistics
            self.query_count += 1
            self.total_processing_time += processing_time
            
            # Send final metadata
            yield {
                "type": "metadata",
                "processing_time": processing_time,
                "confidence": self._calculate_confidence(sources_data) if sources_data else 0.0
            }
            
            self.logger.info(f"Streaming chat completed in {processing_time:.3f}s")
            
        except Exception as e:
            self.logger.error(f"Error in streaming chat: {e}")
            yield {"type": "error", "message": str(e)}
    
    def _is_calculation_problem(self, question: str) -> bool:
        """
        Detect if question is a math/physics calculation problem that should use pure LLM
        
        Args:
            question: The user's question
            
        Returns:
            True if it's a calculation problem that should skip retrieval
        """
        question_lower = question.lower()
        
        # Keywords that indicate calculation problems
        calculation_indicators = [
            'find the', 'calculate', 'compute', 'solve for',
            'what is the value', 'determine the',
            'angle of elevation', 'angle of depression',
            'distance from', 'height of',
            'speed of', 'velocity', 'acceleration',
            'how many', 'how much', 'how long',
            'if a', 'from a point', 'from another point',
            'tower stands', 'building stands',
            'ball is thrown', 'object is thrown',
            'train travels', 'car moves',
            'given that', 'such that'
        ]
        
        # Check if question contains calculation indicators
        has_calculation = any(indicator in question_lower for indicator in calculation_indicators)
        
        # Check if question contains numbers (strong indicator of calculation problem)
        has_numbers = any(char.isdigit() for char in question)
        
        # Check if it has units (m, km, degrees, etc.)
        has_units = any(unit in question_lower for unit in [' m ', ' km ', ' cm ', '°', ' degree', ' meter', ' second'])
        
        # It's a calculation problem if it has calculation keywords + numbers
        # OR if it has calculation keywords + units
        is_calculation = has_calculation and (has_numbers or has_units)
        
        if is_calculation:
            self.logger.info(f"Detected calculation problem - will use pure LLM without retrieval")
        
        return is_calculation
    
    def _retrieve_sources_sync(self, question: str, class_num: Optional[int]) -> List[Dict]:
        """Retrieve source documents synchronously (or skip for calculation problems)"""
        
        # Check if this is a calculation problem that should use pure LLM
        if self._is_calculation_problem(question):
            self.logger.info("Skipping retrieval for calculation problem - using pure LLM mode")
            return []  # Return empty sources to trigger pure LLM mode
        
        # Call RAG pipeline's retrieval method for conceptual questions
        return self.rag_pipeline.retrieve_documents(question, class_num)
    
    async def _generate_answer_stream(
        self,
        question: str,
        sources: List[Dict],
        conversation_history: Optional[List[Dict]] = None
    ):
        """Stream answer generation word-by-word"""
        loop = asyncio.get_event_loop()
        
        # Get the generator from RAG pipeline
        generator = await loop.run_in_executor(
            None,
            self.rag_pipeline.generate_answer_stream,
            question,
            sources,
            conversation_history
        )
        
        # Stream each token/word as it's generated
        for token in generator:
            yield {"type": "token", "content": token}
            await asyncio.sleep(0)  # Allow other tasks to run
    
    def _process_query_sync(self, question: str, class_num: Optional[int], conversation_history: Optional[List[Dict]] = None) -> RAGResponse:
        """Process query synchronously (for thread pool execution)"""
        return self.rag_pipeline.process_query(question, class_num, conversation_history)
    
    def _convert_rag_response(
        self,
        rag_response: RAGResponse,
        request: ChatRequest,
        processing_time: float
    ) -> ChatResponse:
        """Convert RAG pipeline response to API response format"""
        
        # Convert source documents
        sources = []
        rag_sources = rag_response.sources if isinstance(rag_response.sources, list) else []
        if request.include_sources and rag_sources:
            for i, source in enumerate(rag_sources[:request.max_sources]):
                source_doc = SourceDocument(
                    content=source.get('content', ''),
                    metadata=source.get('metadata', {}),
                    source_class=source.get('source_class'),
                    rank=i + 1
                )
                sources.append(source_doc)
        
        # Calculate confidence based on source quality and count
        confidence = self._calculate_confidence(rag_response.sources)
        
        # Enhanced metadata
        metadata = {
            **rag_response.metadata,
            'request_class_num': request.class_num,
            'sources_included': len(sources),
            'cache_hit': rag_response.cache_hit,
            'service_version': '1.0.0'
        }
        
        return ChatResponse(
            answer=rag_response.answer,
            sources=sources,
            confidence=confidence,
            processing_time=processing_time,
            metadata=metadata
        )
    
    def _calculate_confidence(self, sources: List[Dict[str, Any]]) -> float:
        """Calculate confidence score based on source count"""
        if not sources:
            return 0.0
        
        # Base confidence on number of sources found
        # More sources generally means better answer
        base_confidence = min(0.7, 0.3 + len(sources) * 0.1)
        
        return min(1.0, base_confidence)
    
    async def search_documents(
        self,
        request: QueryRequest,
        user_context: UserContext
    ) -> QueryResponse:
        """
        Search for documents based on query
        
        Args:
            request: Search request
            user_context: User context information
            
        Returns:
            Search results
        """
        if not self._initialized:
            raise ServiceUnavailableError("RAG Manager", "Service not initialized")
        
        start_time = time.time()
        
        try:
            self.logger.info(
                f"Processing search request from user {user_context.username}: "
                f"{request.question[:100]}..."
            )
            
            # Use the RAG pipeline's retrieval functionality
            loop = asyncio.get_event_loop()
            documents = await loop.run_in_executor(
                None,
                self._search_documents_sync,
                request
            )
            
            processing_time = time.time() - start_time
            
            # Convert to response format
            source_docs = []
            for i, doc in enumerate(documents[:request.top_k]):
                source_doc = SourceDocument(
                    content=doc.get('content', ''),
                    metadata=doc.get('metadata', {}),
                    source_class=doc.get('source_class'),
                    rank=i + 1
                )
                source_docs.append(source_doc)
            
            response = QueryResponse(
                answer="",  # No answer generated for document search
                results=source_docs,
                total_results=len(documents),
                processing_time=processing_time,
                query_metadata={
                    'class_num': request.class_num,
                    'requested_top_k': request.top_k
                }
            )
            
            self.logger.info(
                f"Search completed in {processing_time:.3f}s, "
                f"found {len(source_docs)} results"
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing search request: {e}")
            raise QueryProcessingError(str(e))
    
    def _search_documents_sync(self, request: QueryRequest) -> List[Dict[str, Any]]:
        """Search documents synchronously (for thread pool execution)"""
        return self.rag_pipeline._retrieve_documents(
            request.question,
            request.class_num,
            request.top_k
        )
    
    async def get_database_status(self) -> DatabaseStatus:
        """Get database status information"""
        if not self._initialized:
            raise ServiceUnavailableError("RAG Manager", "Service not initialized")
        
        try:
            loop = asyncio.get_event_loop()
            status_data = await loop.run_in_executor(
                None,
                self._get_database_status_sync
            )
            
            collections = []
            total_docs = 0
            
            for class_num in range(1, 13):
                collection_name = f"class{class_num}"
                try:
                    count = status_data.get(collection_name, {}).get('document_count', 0)
                    collections.append(CollectionInfo(
                        name=collection_name,
                        document_count=count,
                        class_number=class_num
                    ))
                    total_docs += count
                except Exception as e:
                    self.logger.warning(f"Error getting stats for {collection_name}: {e}")

            # Return database status with explicit connected/status fields
            return DatabaseStatus(
                connected=True,
                collections=collections,
                total_documents=total_docs,
                status=("healthy" if total_docs > 0 else "empty")
            )
            
        except Exception as e:
            self.logger.error(f"Error getting database status: {e}")
            raise ChromaDBError(str(e))
    
    def _get_database_status_sync(self) -> Dict[str, Any]:
        """Get database status synchronously"""
        return self.rag_pipeline.get_collection_stats()
    
    async def get_service_stats(self) -> StatsResponse:
        """Get service statistics"""
        database_status = await self.get_database_status()
        
        cache_hit_rate = (
            (self.cache_hits / max(1, self.query_count)) * 100
        )
        
        avg_processing_time = (
            self.total_processing_time / max(1, self.query_count)
        )
        
        uptime = time.time() - self.start_time
        
        return StatsResponse(
            total_queries=self.query_count,
            cache_hit_rate=cache_hit_rate,
            average_processing_time=avg_processing_time,
            database_status=database_status,
            uptime=uptime
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            if not self._initialized:
                return {
                    "status": "unhealthy",
                    "reason": "Service not initialized"
                }
            
            # Quick health check
            loop = asyncio.get_event_loop()
            db_check = await loop.run_in_executor(
                None,
                self._quick_health_check
            )
            
            return {
                "status": "healthy" if db_check else "unhealthy",
                "initialized": self._initialized,
                "queries_processed": self.query_count,
                "uptime": time.time() - self.start_time,
                "database_accessible": db_check
            }
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def _quick_health_check(self) -> bool:
        """Quick health check (runs in thread pool)"""
        try:
            # Test database connection
            stats = self.rag_pipeline.get_collection_stats()
            return len(stats) > 0
        except Exception:
            return False
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            self.logger.info("Cleaning up RAG Manager...")
            
            if self.rag_pipeline:
                # Cleanup RAG pipeline resources in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._cleanup_pipeline)
            
            self._initialized = False
            self.logger.info("RAG Manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def _cleanup_pipeline(self) -> None:
        """Cleanup pipeline resources (runs in thread pool)"""
        try:
            # The RAG pipeline will handle its own cleanup
            if hasattr(self.rag_pipeline, 'cleanup'):
                self.rag_pipeline.cleanup()
        except Exception as e:
            self.logger.error(f"Error cleaning up pipeline: {e}")
    
    def clear_cache(self) -> Dict[str, Any]:
        """Clear the RAG pipeline cache"""
        try:
            if self.rag_pipeline:
                cache_size_before = len(getattr(self.rag_pipeline, '_cache', {}))
                self.rag_pipeline.clear_cache()
                self.logger.info(f"Cache cleared successfully. Removed {cache_size_before} cached items.")
                return {
                    "status": "success",
                    "message": f"Cache cleared successfully. Removed {cache_size_before} cached items.",
                    "items_cleared": cache_size_before
                }
            else:
                return {
                    "status": "error",
                    "message": "RAG pipeline not initialized"
                }
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            return {
                "status": "error",
                "message": f"Failed to clear cache: {str(e)}"
            }