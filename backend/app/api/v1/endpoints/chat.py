"""
Chat endpoints for the SAGE RAG API

Handles chat requests, conversation management, and real-time messaging.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.models import (
    ChatRequest,
    ChatResponse,
    UserContext,
    ErrorResponse
)
from app.services.rag_manager import RAGManager
from app.core.exceptions import RAGException
from app.api.dependencies import get_rag_manager, get_user_context, get_optional_user_context

router = APIRouter()
logger = logging.getLogger("api.chat")


@router.post(
    "/ask",
    response_model=ChatResponse,
    summary="Ask a question to the AI tutor",
    description="Submit a question and get an AI-generated answer with supporting sources from NCERT curriculum"
)
async def ask_question(
    request: ChatRequest,
    user_context: UserContext = Depends(get_optional_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> ChatResponse:
    """
    Process a chat question and return an AI-generated answer
    
    - **message**: The student's question (required)
    - **class_num**: Target class number (1-12), optional for cross-class search
    - **conversation_history**: Previous messages for context
    - **include_sources**: Whether to include source documents
    - **max_sources**: Maximum number of source documents to return
    """
    try:
        logger.info(
            f"Chat request from {user_context.username if user_context else 'anonymous'} "
            f"(role: {user_context.role if user_context else 'guest'}): {request.message[:100]}..."
        )
        
        # Create default user context if not authenticated
        if not user_context:
            from app.models import UserRole
            user_context = UserContext(
                user_id="dev-user",
                username="guest",
                role=UserRole.STUDENT,
                email=None,
                school_id=None
            )
        
        # For students, limit to their relevant classes if not specified
        if user_context.role == "student" and request.class_num is None:
            # You could implement grade-level restrictions here
            pass
        
        response = await rag_manager.process_chat(request, user_context)
        
        logger.info(
            f"Chat response generated for {user_context.username if user_context else 'anonymous'}: "
            f"{len(response.answer)} chars, {len(response.sources)} sources"
        )
        
        return response
        
    except RAGException as e:
        logger.error(f"RAG error in chat endpoint: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/ask/stream",
    summary="Ask a question with streaming response",
    description="Submit a question and get an AI-generated answer streamed word-by-word"
)
async def ask_question_stream(
    request: ChatRequest,
    user_context: UserContext = Depends(get_optional_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
):
    """
    Process a chat question and stream the response as it's generated
    
    Returns a Server-Sent Events (SSE) stream with the answer being generated
    in real-time, followed by sources.
    """
    import json
    import asyncio
    
    async def generate_stream():
        try:
            # Create default user context if not authenticated
            nonlocal user_context
            if not user_context:
                from app.models import UserRole
                user_context = UserContext(
                    user_id="dev-user",
                    username="guest",
                    role=UserRole.STUDENT,
                    email=None,
                    school_id=None
                )
            
            logger.info(
                f"Streaming chat request from {user_context.username}: "
                f"{request.message[:100]}..."
            )
            
            # Stream the response
            async for chunk in rag_manager.process_chat_stream(request, user_context):
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0)  # Allow other tasks to run
            
            # Send done signal
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            error_data = {
                "error": True,
                "message": "An error occurred while generating the response"
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post(
    "/conversation",
    response_model=ChatResponse,
    summary="Continue a conversation",
    description="Continue an existing conversation with context awareness"
)
async def continue_conversation(
    request: ChatRequest,
    conversation_id: str,
    user_context: UserContext = Depends(get_user_context),
    rag_manager: RAGManager = Depends(get_rag_manager)
) -> ChatResponse:
    """
    Continue an existing conversation with full context
    
    This endpoint maintains conversation state and provides more contextual responses
    based on the conversation history.
    """
    try:
        logger.info(
            f"Conversation continuation from {user_context.username} "
            f"(conversation: {conversation_id}): {request.message[:100]}..."
        )
        
        # Add conversation ID to the request context
        response = await rag_manager.process_chat(request, user_context)
        response.conversation_id = conversation_id
        
        return response
        
    except RAGException as e:
        logger.error(f"RAG error in conversation endpoint: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error in conversation endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/suggestions",
    summary="Get question suggestions",
    description="Get suggested questions based on class and topic"
)
async def get_question_suggestions(
    class_num: int = None,
    topic: str = None,
    limit: int = 5,
    user_context: UserContext = Depends(get_user_context)
) -> Dict[str, Any]:
    """
    Get suggested questions for students based on their class level and topics
    
    - **class_num**: Class number (1-12)
    - **topic**: Topic filter (optional)
    - **limit**: Number of suggestions to return
    """
    try:
        # Predefined suggestions for different classes and topics
        suggestions = _get_predefined_suggestions(class_num, topic, limit)
        
        return {
            "suggestions": suggestions,
            "class_num": class_num,
            "topic": topic,
            "count": len(suggestions)
        }
        
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get suggestions")


def _get_predefined_suggestions(class_num: int, topic: str, limit: int) -> list:
    """Get predefined question suggestions"""
    
    # Sample suggestions by class and topic
    suggestions_db = {
        1: {
            "math": [
                "What are numbers?",
                "How do we count things?",
                "What are shapes?",
                "How do we add numbers?",
                "What is subtraction?"
            ],
            "english": [
                "What are letters?",
                "How do we read words?",
                "What is a sentence?",
                "What are vowels?",
                "How do we write stories?"
            ]
        },
        5: {
            "math": [
                "What are fractions?",
                "How do we multiply numbers?",
                "What is division?",
                "What are decimals?",
                "How do we measure area?"
            ],
            "science": [
                "What is the solar system?",
                "How do plants grow?",
                "What is water cycle?",
                "What are different animals?",
                "How do we breathe?"
            ]
        },
        10: {
            "math": [
                "What are real numbers?",
                "How do we solve quadratic equations?",
                "What is coordinate geometry?",
                "What are trigonometric ratios?",
                "How do we find area of circles?"
            ],
            "science": [
                "What is photosynthesis?",
                "How does digestion work?",
                "What are acids and bases?",
                "What is electromagnetic induction?",
                "How do we inherit traits?"
            ]
        }
    }
    
    # Get suggestions for the specified class
    class_suggestions = suggestions_db.get(class_num, {})
    
    if topic and topic.lower() in class_suggestions:
        suggestions = class_suggestions[topic.lower()]
    else:
        # Return suggestions from all topics for this class
        suggestions = []
        for topic_suggestions in class_suggestions.values():
            suggestions.extend(topic_suggestions)
    
    # Return limited number of suggestions
    return suggestions[:limit] if suggestions else [
        "What would you like to learn today?",
        "Can you help me understand this topic?",
        "How does this concept work?",
        "Can you explain this with examples?",
        "What are the key points I should remember?"
    ]