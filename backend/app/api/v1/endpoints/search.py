from typing import Any
from typing import Dict
from app.services.rag_manager import RAGManager
from app.api.dependencies import get_rag_manager, get_user_context
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
router = APIRouter()
logger = logging.getLogger("api.search")

@router.get(
    "/search",
    summary="Simple search status endpoint",
    description="Returns a status or performs a lightweight search for l_search integration."
)
async def l_search(
    query: str = Query(default=None, description="Search query text", required=False),
    class_num: int = Query(default=None, description="Class number filter", required=False),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> Dict[str, Any]:
    """
    Lightweight search endpoint for l_search integration or status check.
    """
    if query is not None and query != "":
        try:
            docs = await rag_manager.search_documents(
                QueryRequest(question=query, class_num=class_num, include_sources=False),
                UserContext(user_id="system", username="system", role="ADMIN")
            )
            return {"status": "ok", "results": [doc.content for doc in docs.results]}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": "l_search endpoint active"}
"""
Search endpoints for the SAGE RAG API

Handles document search, content retrieval, and knowledge base queries.
"""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import (
    QueryRequest,
    QueryResponse,
    UserContext,
    BulkQueryRequest,
    BulkQueryResponse
)
from app.services.rag_manager import RAGManager
from app.core.exceptions import RAGException
from app.api.dependencies import get_rag_manager, get_user_context

router = APIRouter()
logger = logging.getLogger("api.search")


@router.post(
    "/documents",
    response_model=QueryResponse,
    summary="Search for documents",
    description="Search for relevant documents from the NCERT curriculum database"
)
async def search_documents(
    request: QueryRequest,
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> QueryResponse:
    """
    Search for documents in the knowledge base
    
    - **query**: Search query text (required)
    - **class_num**: Target class number (1-12), optional for cross-class search
    - **top_k**: Number of results to return (1-20)
    - **similarity_threshold**: Minimum similarity score (0.0-1.0)
    """
    try:
        logger.info(
            f"Document search from {user_context.username}: "
            f"{request.question[:100]}..."
        )
        
        response = await rag_manager.search_documents(request, user_context)
        
        logger.info(
            f"Search completed for {user_context.username}: "
            f"{response.total_results} results found"
        )
        
        return response
        
    except RAGException as e:
        logger.error(f"RAG error in search endpoint: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error in search endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/topics",
    summary="Search by topic",
    description="Search for content related to specific topics"
)
async def search_by_topic(
    topic: str = Query(..., description="Topic to search for"),
    class_num: int = Query(None, ge=1, le=12, description="Class number filter"),
    limit: int = Query(5, ge=1, le=20, description="Number of results"),
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> QueryResponse:
    """
    Search for content by topic name
    
    Useful for exploring specific subjects or concepts across the curriculum.
    """
    try:
        # Create a query request for topic search
        request = QueryRequest(
            question=topic,
            class_num=class_num,
            top_k=limit,
            similarity_threshold=0.3  # Lower threshold for topic exploration
        )
        
        response = await rag_manager.search_documents(request, user_context)
        
        return response
        
    except RAGException as e:
        logger.error(f"RAG error in topic search: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error in topic search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/class/{class_num}/overview",
    summary="Get class overview",
    description="Get an overview of content available for a specific class"
)
async def get_class_overview(
    class_num: int,
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> Dict[str, Any]:
    """
    Get an overview of content available for a specific class
    
    Returns statistics and sample content for the specified class.
    """
    try:
        if not (1 <= class_num <= 12):
            raise HTTPException(status_code=422, detail="Class number must be between 1 and 12")
        
        logger.info(f"Class overview request for class {class_num} from {user_context.username}")
        
        # Get basic statistics
        db_status = await rag_manager.get_database_status()
        
        # Find the collection for this class
        class_collection = None
        for collection in db_status.collections:
            if collection.name == f"class{class_num}":
                class_collection = collection
                break
        
        if not class_collection:
            return {
                "class_num": class_num,
                "status": "no_content",
                "document_count": 0,
                "subjects": [],
                "sample_topics": []
            }
        
        # Get sample content by searching for common terms
        sample_queries = ["introduction", "chapter", "definition", "example"]
        sample_topics = []
        
        for query in sample_queries:
            try:
                request = QueryRequest(
                    query=query,
                    class_num=class_num,
                    top_k=2,
                    similarity_threshold=0.2
                )
                
                response = await rag_manager.search_documents(request, user_context)
                
                for result in response.results:
                    # Extract topic information from metadata
                    subject = result.metadata.get('subject', 'general')
                    if subject not in [topic['subject'] for topic in sample_topics]:
                        sample_topics.append({
                            'subject': subject,
                            'content_preview': result.content[:200] + "..." if len(result.content) > 200 else result.content
                        })
                    
                    if len(sample_topics) >= 5:
                        break
                        
                if len(sample_topics) >= 5:
                    break
                    
            except Exception as e:
                logger.warning(f"Error sampling content for class {class_num}: {e}")
                continue
        
        # Extract unique subjects
        subjects = list(set(topic['subject'] for topic in sample_topics))
        
        return {
            "class_num": class_num,
            "status": "available",
            "document_count": class_collection.document_count,
            "subjects": subjects,
            "sample_topics": sample_topics[:5]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting class overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to get class overview")


@router.post(
    "/bulk",
    response_model=BulkQueryResponse,
    summary="Bulk search queries",
    description="Process multiple search queries in batch"
)
async def bulk_search(
    request: BulkQueryRequest,
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> BulkQueryResponse:
    """
    Process multiple search queries in batch
    
    Useful for analyzing multiple topics or questions simultaneously.
    """
    try:
        logger.info(
            f"Bulk search request from {user_context.username}: "
            f"{len(request.queries)} queries"
        )
        
        results = []
        successful_queries = 0
        failed_queries = 0
        start_time = time.time()
        
        if request.parallel:
            # Process queries in parallel (limited concurrency)
            import asyncio
            semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent queries
            
            async def process_single_query(query_req):
                async with semaphore:
                    try:
                        return await rag_manager.search_documents(query_req, user_context)
                    except Exception as e:
                        logger.error(f"Error in bulk query: {e}")
                        return None
            
            # Create tasks for all queries
            tasks = [process_single_query(query) for query in request.queries]
            query_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(query_results):
                if isinstance(result, Exception) or result is None:
                    failed_queries += 1
                    # Add empty result for failed query
                    results.append(QueryResponse(
                        results=[],
                        total_results=0,
                        processing_time=0.0,
                        query_metadata={"error": "Query failed", "query_index": i}
                    ))
                else:
                    successful_queries += 1
                    results.append(result)
        else:
            # Process queries sequentially
            for i, query_req in enumerate(request.queries):
                try:
                    result = await rag_manager.search_documents(query_req, user_context)
                    results.append(result)
                    successful_queries += 1
                except Exception as e:
                    logger.error(f"Error processing query {i}: {e}")
                    failed_queries += 1
                    results.append(QueryResponse(
                        results=[],
                        total_results=0,
                        processing_time=0.0,
                        query_metadata={"error": str(e), "query_index": i}
                    ))
        
        total_processing_time = time.time() - start_time
        
        response = BulkQueryResponse(
            results=results,
            total_processing_time=total_processing_time,
            successful_queries=successful_queries,
            failed_queries=failed_queries
        )
        
        logger.info(
            f"Bulk search completed for {user_context.username}: "
            f"{successful_queries} successful, {failed_queries} failed"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in bulk search: {e}")
        raise HTTPException(status_code=500, detail="Bulk search failed")


# Add this import at the top
import time