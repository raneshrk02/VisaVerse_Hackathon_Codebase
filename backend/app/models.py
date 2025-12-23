"""
Pydantic models for the SAGE RAG API

This module defines all the request and response models used by the FastAPI endpoints.
"""

from typing import List, Dict, Any, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field #type: ignore
from datetime import datetime


class UserRole(str, Enum):
    """User role enumeration"""
    STUDENT = "student"
    ADMIN = "admin"
    ROOT_ADMIN = "root_admin"


class UserContext(BaseModel):
    """User context information"""
    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: Optional[str] = Field(None, description="User email address")
    role: UserRole = Field(..., description="User role")
    school_id: Optional[str] = Field(None, description="School identifier")


class ChatMessage(BaseModel):
    """Individual chat message"""
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[int] = Field(None, description="Message timestamp")


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., description="User's question")
    class_num: Optional[int] = Field(None, description="Target class number (1-12)")
    conversation_history: List[ChatMessage] = Field(default=[], description="Previous conversation messages")
    include_sources: bool = Field(default=True, description="Include source documents in response")
    max_sources: int = Field(default=5, description="Maximum number of source documents to return")


class SourceDocument(BaseModel):
    """Source document model"""
    content: str = Field(..., description="Document content")
    metadata: Dict[str, Any] = Field(default={}, description="Document metadata")
    source_class: Optional[int] = Field(None, description="Source class number")
    rank: int = Field(..., description="Ranking position")


class ChatResponse(BaseModel):
    """Chat response model"""
    answer: str = Field(..., description="AI-generated answer")
    sources: List[SourceDocument] = Field(default=[], description="Supporting source documents")
    confidence: float = Field(..., description="Response confidence score")
    processing_time: float = Field(..., description="Processing time in seconds")
    metadata: Dict[str, Any] = Field(default={}, description="Response metadata")
    cache_hit: bool = Field(default=False, description="Whether response came from cache")
    conversation_id: Optional[str] = Field(None, description="Conversation identifier")


class QueryRequest(BaseModel):
    """Generic query request model"""
    question: str = Field(..., description="Question to ask")
    class_num: Optional[int] = Field(None, description="Target class number")
    include_sources: bool = Field(default=True, description="Include source documents")
    top_k: int = Field(default=5, description="Number of results to return")
    similarity_threshold: float = Field(default=0.5, description="Minimum similarity score")


class QueryResponse(BaseModel):
    """Generic query response model for document search"""
    answer: str = Field(..., description="Generated answer")
    results: List[SourceDocument] = Field(default=[], description="Search results")
    total_results: int = Field(default=0, description="Total number of results found")
    processing_time: float = Field(default=0.0, description="Search processing time in seconds")
    query_metadata: Dict[str, Any] = Field(default={}, description="Additional query metadata")


class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., description="Search query")
    class_num: Optional[int] = Field(None, description="Target class number")
    max_results: int = Field(default=10, description="Maximum number of results")


class SearchResponse(BaseModel):
    """Search response model"""
    documents: List[SourceDocument] = Field(..., description="Search results")
    total_found: int = Field(..., description="Total number of documents found")
    processing_time: float = Field(..., description="Search processing time")


class CollectionInfo(BaseModel):
    """Collection information model"""
    name: str = Field(..., description="Collection name")
    document_count: int = Field(..., description="Number of documents")
    class_number: Optional[int] = Field(None, description="Associated class number")


class DatabaseStatus(BaseModel):
    """Database status model"""
    connected: bool = Field(..., description="Database connection status")
    total_documents: int = Field(default=0, description="Total documents in database")
    collections: List[CollectionInfo] = Field(default=[], description="Available collections")
    status: Optional[str] = Field(None, description="Health status string (e.g. healthy/empty)")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")


class StatsResponse(BaseModel):
    """System statistics response model"""
    total_queries: int = Field(..., description="Total number of queries processed")
    cache_hit_rate: float = Field(..., description="Cache hit rate percentage")
    average_processing_time: float = Field(..., description="Average processing time")
    database_status: DatabaseStatus = Field(..., description="Database status information")
    uptime: float = Field(..., description="System uptime in seconds")
    success: bool = Field(default=True, description="Response success status")
    error_message: Optional[str] = Field(None, description="Error message if any")


class HealthStatus(BaseModel):
    """Health check status model"""
    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    services: Dict[str, bool] = Field(default={}, description="Individual service statuses")
    uptime: float = Field(..., description="Service uptime")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")


class BatchIndexRequest(BaseModel):
    """Batch indexing request model"""
    class_num: int = Field(..., description="Target class number")
    questions_file_path: str = Field(..., description="Path to questions file")


class BatchIndexResponse(BaseModel):
    """Batch indexing response model"""
    success: bool = Field(..., description="Indexing success status")
    total_questions: int = Field(..., description="Total questions processed")
    total_paraphrases: int = Field(..., description="Total paraphrases generated")
    processing_time: float = Field(..., description="Total processing time")
    error_count: int = Field(default=0, description="Number of errors encountered")


class BulkQueryRequest(BaseModel):
    """Bulk query request model"""
    queries: List[str] = Field(..., description="List of queries to process")
    class_num: Optional[int] = Field(None, description="Target class number")
    include_sources: bool = Field(default=True, description="Include source documents")
    max_sources: int = Field(default=5, description="Maximum sources per query")


class BulkQueryResponse(BaseModel):
    """Bulk query response model"""
    results: List[QueryResponse] = Field(..., description="Query results")
    total_queries: int = Field(..., description="Total number of queries processed")
    successful_queries: int = Field(..., description="Number of successful queries")
    failed_queries: int = Field(..., description="Number of failed queries")
    total_processing_time: float = Field(..., description="Total processing time")