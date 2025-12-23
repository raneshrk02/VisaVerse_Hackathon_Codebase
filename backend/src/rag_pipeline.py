"""
RAG Pipeline Module - OPTIMIZED VERSION

This module implements the complete Retrieval-Augmented Generation pipeline
that orchestrates ChromaDB operations and Phi-2 model inference to provide
accurate answers to educational questions.

Features:
- Complete RAG workflow
- Intelligent caching with LRU mechanism
- Parallel processing for multi-class searches
- Comprehensive error handling and logging
- Batch indexing capabilities
- Performance monitoring and metadata tracking
"""

import json
import csv
import time
import logging
from functools import lru_cache
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent.futures

from .db_handler import ChromaDBHandler
from .llm_handler import Phi2Handler
from .config_loader import Config


@dataclass
class RAGResponse:
    """Structured response from RAG pipeline."""
    answer: str
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    cache_hit: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary format."""
        return {
            "answer": self.answer,
            "sources": self.sources,
            "metadata": self.metadata,
            "cache_hit": self.cache_hit
        }


class RAGPipeline:
    """
    Complete Retrieval-Augmented Generation Pipeline.
    
    This class orchestrates the entire RAG workflow including:
    - Document retrieval from ChromaDB
    - Context-aware answer generation
    - Performance monitoring and caching
    """
    
    def __init__(self, config: Config):
        """
        Initialize RAG pipeline with configuration.
        
        Args:
            config: Configuration object containing all settings
        """
        self.config = config
        self.logger = self._setup_logging()
        
        # Initialize components
        try:
            self.db_handler = ChromaDBHandler(config)
            self.llm_handler = Phi2Handler(config)
            self.logger.info("RAG pipeline initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize RAG pipeline: {e}")
            raise
        
        # Cache for query responses (LRU with max 100 entries)
        self._cache = {}
        self._cache_order = []
        self._max_cache_size = 100
        
        # Performance tracking
        self._query_stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "avg_processing_time": 0.0
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger(f"RAGPipeline")
        
        if not logger.handlers:
            # Create logs directory if it doesn't exist
            log_dir = Path(self.config.paths.logs_dir)
            log_dir.mkdir(exist_ok=True)
            
            # File handler
            log_file = log_dir / "rag_pipeline.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(getattr(logging, self.config.logging.level))
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            logger.setLevel(getattr(logging, self.config.logging.level))
        
        return logger
    
    def _generate_cache_key(self, question: str, class_num: Optional[int], conversation_context: str = "") -> str:
        """Generate cache key for query including conversation context."""
        class_key = "ALL" if class_num is None else str(class_num)
        # Include conversation context in cache key to ensure context-aware caching
        context_hash = hash(conversation_context) if conversation_context else 0
        return f"{class_key}:{hash(question.lower().strip())}:{context_hash}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[RAGResponse]:
        """Retrieve response from cache."""
        if cache_key in self._cache:
            # Move to end (most recently used)
            self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)
            
            response = self._cache[cache_key]
            response.cache_hit = True
            return response
        return None
    
    def _add_to_cache(self, cache_key: str, response: RAGResponse):
        """Add response to cache with LRU eviction."""
        # Remove oldest entries if cache is full
        while len(self._cache) >= self._max_cache_size:
            oldest_key = self._cache_order.pop(0)
            del self._cache[oldest_key]
        
        # Add new entry
        self._cache[cache_key] = response
        self._cache_order.append(cache_key)
    
    def _validate_inputs(self, question: str, class_num: Optional[int]) -> None:
        """
        Validate input parameters.
        
        Args:
            question: Question text to validate
            class_num: Class number to validate or None for all classes
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        if class_num is not None and (not isinstance(class_num, int) or class_num < 1 or class_num > 12):
            raise ValueError("Class number must be between 1 and 12 or None for all classes")
        
        if len(question.strip()) > 1000:
            raise ValueError("Question is too long (max 1000 characters)")
    
    def _generate_paraphrases(self, question: str, enable_paraphrasing: bool = True) -> List[str]:
        """
        Generate paraphrased versions of the question (OPTIMIZED).
        
        Args:
            question: Original question
            enable_paraphrasing: Whether to enable paraphrasing (for speed mode)
            
        Returns:
            List of paraphrased questions
        """
        if not enable_paraphrasing:
            self.logger.info("[OPTIMIZATION] Paraphrasing DISABLED for speed (config: enable_paraphrasing=false)")
            return []
            
        try:
            self.logger.debug(f"Generating paraphrases for: {question}")
            paraphrases = self.llm_handler.generate_paraphrases(question)
            self.logger.debug(f"Generated {len(paraphrases)} paraphrases")
            return paraphrases
        except Exception as e:
            self.logger.error(f"Failed to generate paraphrases: {e}")
            # Return empty list if paraphrasing fails
            return []
    
    def _insert_questions(self, questions: List[str], class_num: int) -> None:
        """
        Insert questions into ChromaDB collection.
        
        Args:
            questions: List of questions to insert
            class_num: Target class number
        """
        try:
            for question in questions:
                self.db_handler.add_question(class_num, question)
            self.logger.debug(f"Inserted {len(questions)} questions into class{class_num}")
        except Exception as e:
            self.logger.error(f"Failed to insert questions: {e}")
            # Don't raise - retrieval might still work with existing data
    
    def _search_single_class(self, class_number: int, question: str, docs_per_class: int) -> List[Dict[str, Any]]:
        """
        Search a single class collection (for parallel processing).
        
        Args:
            class_number: Class number to search
            question: Query question
            docs_per_class: Number of documents to retrieve per class
            
        Returns:
            List of documents from this class
        """
        try:
            results = self.db_handler.retrieve_similar(class_number, question, docs_per_class)
            
            documents = []
            if results and results.get('documents') and results['documents'][0]:
                for doc, metadata, distance in zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                ):
                    similarity_score = max(0, 1.0 - distance)
                    document = {
                        'content': doc,
                        'metadata': metadata,
                        'similarity_score': similarity_score,
                        'distance': distance,
                        'source_class': class_number
                    }
                    documents.append(document)
            return documents
        except Exception as e:
            self.logger.warning(f"Failed to retrieve from class{class_number}: {e}")
            return []
    
    def _retrieve_documents(self, question: str, class_num: Optional[int], n_results: int = 3, parallel_search: bool = True) -> List[Dict[str, Any]]:
        """
        Retrieve similar documents from ChromaDB (OPTIMIZED with parallel search).
        
        Args:
            question: Query question
            class_num: Class number for collection or None for all classes
            n_results: Number of results to retrieve
            parallel_search: Enable parallel search across classes
            
        Returns:
            List of retrieved documents with metadata
        """
        try:
            if class_num is None:
                self.logger.debug("Retrieving documents from ALL classes")
                all_documents = []
                
                if parallel_search:
                    # OPTIMIZATION: Parallel search with thread pool
                    docs_per_class = max(1, n_results // 4)
                    priority_classes = [6, 7, 8, 9, 10, 11, 12]  # Focus on higher classes
                    
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        future_to_class = {
                            executor.submit(self._search_single_class, class_number, question, docs_per_class): class_number
                            for class_number in priority_classes
                        }
                        
                        for future in as_completed(future_to_class, timeout=5.0):
                            try:
                                class_docs = future.result(timeout=2.0)
                                all_documents.extend(class_docs)
                            except Exception as e:
                                self.logger.warning(f"Parallel search timeout/error: {e}")
                                continue
                else:
                    # Sequential search (fallback)
                    for class_number in range(1, 13):
                        try:
                            docs_per_class = max(1, n_results // 6)
                            results = self.db_handler.retrieve_similar(class_number, question, docs_per_class)
                            
                            if results and results.get('documents') and results['documents'][0]:
                                for doc, metadata, distance in zip(
                                    results['documents'][0],
                                    results['metadatas'][0],
                                    results['distances'][0]
                                ):
                                    similarity_score = max(0, 1.0 - distance)
                                    document = {
                                        'content': doc,
                                        'metadata': metadata,
                                        'similarity_score': similarity_score,
                                        'distance': distance,
                                        'source_class': class_number
                                    }
                                    all_documents.append(document)
                        except Exception as e:
                            self.logger.warning(f"Failed to retrieve from class{class_number}: {e}")
                            continue
                
                # Sort by similarity and take top results
                all_documents.sort(key=lambda x: x['distance'])
                documents = all_documents[:n_results]
                
                self.logger.debug(f"Retrieved {len(documents)} documents from all classes")
                return documents
            else:
                self.logger.debug(f"Retrieving documents for class{class_num}")
                results = self.db_handler.retrieve_similar(class_num, question, n_results)
                
                if not results or not results.get('documents') or not results['documents'][0]:
                    self.logger.warning(f"No documents retrieved for class{class_num}")
                    return []
                
                # Format results with scores
                documents = []
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    # Convert distance to similarity score (0-1)
                    similarity_score = max(0, 1 - distance)
                    
                    documents.append({
                        'content': doc,
                        'metadata': metadata or {},
                        'similarity_score': round(similarity_score, 4),
                        'rank': i + 1,
                        'source_class': class_num
                    })
                
                self.logger.debug(f"Retrieved {len(documents)} documents from class{class_num}")
                return documents
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve documents: {e}")
            return []
    
    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """
        Format retrieved documents into context string.
        
        Args:
            documents: List of retrieved documents
            
        Returns:
            Formatted context string
        """
        if not documents:
            return "No relevant documents found."
        
        context_parts = []
        for doc in documents:
            score = doc['similarity_score']
            content = doc['content']
            
            # Only include highly relevant documents (similarity > 0.3)
            if score > 0.3:
                context_parts.append(f"[Relevance: {score:.2f}] {content}")
        
        if not context_parts:
            return "No highly relevant documents found."
        
        return "\n\n".join(context_parts)
    
    def _is_math_or_physics_question(self, question: str, documents: List[Dict[str, Any]]) -> bool:
        """Detect if question is about math/physics/chemistry (benefits from step-by-step)."""
        question_lower = question.lower()
        
        # Keywords that indicate math/physics/chemistry problems
        keywords = [
            'solve', 'calculate', 'find', 'prove', 'derive', 'show that',
            'equation', 'formula', 'expression',
            'vector', 'matrix', 'determinant',
            'force', 'velocity', 'acceleration', 'mass', 'energy', 'work', 'power',
            'reaction', 'balance', 'mole', 'molarity', 'titration', 'synthesis',
            'mechanism', 'isomer', 'compound', 'oxidation', 'reduction',
            'angle', 'triangle', 'circle', 'area', 'volume',
            'sin', 'cos', 'tan', 'log', 'ln',
            'integrate', 'differentiate', 'limit', 'derivative', 'integral',
            'circuit', 'resistance', 'current', 'voltage',
            'probability', 'permutation', 'combination'
        ]
        
        # Check for mathematical notation or numbers with operations
        import re
        has_math_notation = bool(re.search(r'[x-z]\s*[=+\-*/]|\d+\s*[+\-*/×÷]', question_lower))
        
        # Check question
        if any(kw in question_lower for kw in keywords) or has_math_notation:
            return True
        
        # Check document metadata for subject
        for doc in documents:
            metadata = doc.get('metadata', {})
            subject = metadata.get('subject', '').lower()
            if any(subj in subject for subj in ['math', 'physics', 'chemistry']):
                return True
        
        return False
    
    def _generate_answer(self, question: str, documents: List[Dict[str, Any]], class_num: Optional[int], conversation_context: str = "") -> Tuple[str, Dict[str, Any]]:
        """
        Generate answer using LLM with retrieved documents (with hybrid mode support).
        
        Args:
            question: Original question
            documents: Retrieved documents from ChromaDB
            class_num: Class number for context or None for all classes
            conversation_context: Previous conversation context for better answers
            
        Returns:
            Tuple of (answer, metadata)
        """
        try:
            self.logger.debug("Generating answer with LLM")
            
            start_time = time.time()
            
            # Check if hybrid mode is enabled
            hybrid_mode = getattr(self.config.rag.generation, 'hybrid_mode', False)
            use_hybrid = hybrid_mode and self._is_math_or_physics_question(question, documents)
            
            if use_hybrid:
                self.logger.info("[HYBRID_MODE] Detected math/physics/chemistry question - using step-by-step reasoning")
            
            # Pass question, documents, conversation context, and hybrid flag to LLM handler
            answer = self.llm_handler.generate_answer(question, documents, conversation_context, use_hybrid_prompt=use_hybrid)
            generation_time = time.time() - start_time
            
            # Calculate metadata from documents
            total_content_length = sum(len(str(doc)) for doc in documents)
            
            metadata = {
                'generation_time': round(generation_time, 3),
                'documents_count': len(documents),
                'hybrid_mode_used': use_hybrid,
                'total_content_length': total_content_length
            }
            
            self.logger.debug(f"Answer generated in {generation_time:.3f}s")
            return answer, metadata
            
        except Exception as e:
            self.logger.error(f"Failed to generate answer: {e}")
            return f"I apologize, but I encountered an error generating an answer: {str(e)}", {}
    
    def _generate_answer_without_context(self, question: str, class_num: Optional[int], conversation_context: str = "") -> Tuple[str, Dict[str, Any]]:
        """
        Generate answer using LLM without RAG context (pure LLM response).
        Used when no relevant documents are found in the knowledge base.
        
        Args:
            question: Original question
            class_num: Class number for context or None for all classes
            conversation_context: Previous conversation context
            
        Returns:
            Tuple of (answer, metadata)
        """
        try:
            self.logger.info("Generating answer using LLM without RAG context")
            
            start_time = time.time()
            
            # Check if this is a math/science problem that needs step-by-step solving
            is_math_problem = self._is_math_or_science_problem(question)
            
            # Generate answer without document context
            answer = self.llm_handler.generate_answer_without_context(
                question, 
                class_num=class_num,
                conversation_context=conversation_context,
                use_step_by_step=is_math_problem
            )
            
            generation_time = time.time() - start_time
            
            metadata = {
                'generation_time': round(generation_time, 3),
                'documents_count': 0,
                'pure_llm_mode': True,
                'math_problem_detected': is_math_problem
            }
            
            self.logger.info(f"Answer generated without context in {generation_time:.3f}s")
            return answer, metadata
            
        except Exception as e:
            self.logger.error(f"Failed to generate answer without context: {e}")
            raise
    
    def _is_math_or_science_problem(self, question: str) -> bool:
        """
        Detect if the question is a math or science problem that needs step-by-step solving.
        
        Args:
            question: The question text
            
        Returns:
            True if it appears to be a math/science problem
        """
        question_lower = question.lower()
        
        # Keywords that indicate a math/science problem requiring step-by-step solution
        math_keywords = [
            'find', 'calculate', 'compute', 'solve', 'determine', 'derive',
            'angle', 'elevation', 'depression', 'height', 'distance',
            'equation', 'formula', 'prove', 'show that',
            'speed', 'velocity', 'acceleration', 'force', 'mass', 'work', 'energy',
            'area', 'volume', 'perimeter', 'circumference', 'surface area',
            'sin', 'cos', 'tan', 'triangle', 'circle', 'square', 'rectangle',
            'quadratic', 'linear', 'polynomial', 'expression',
            'integrate', 'differentiate', 'derivative', 'integral',
            'reaction', 'balance', 'moles', 'molarity', 'titration',
            'mechanism', 'synthesis', 'isomer', 'compound', 'oxidation',
            'power', 'resistance', 'current', 'voltage', 'circuit',
            'probability', 'permutation', 'combination'
        ]
        
        # Check if question contains math/science keywords
        has_keywords = any(keyword in question_lower for keyword in math_keywords)
        
        # Check if question contains numbers
        import re
        has_numbers = bool(re.search(r'\d+', question))
        
        # Check for "step" in question (e.g., "show steps", "explain step by step")
        asks_for_steps = 'step' in question_lower
        
        return (has_keywords and has_numbers) or asks_for_steps
    
    def process_query(self, question: str, class_num: Optional[int] = None, conversation_history: Optional[List[Dict]] = None) -> RAGResponse:
        """
        Process a complete RAG query workflow.
        
        Args:
            question: User question
            class_num: Target class number (1-12) or None for all classes
            conversation_history: Previous conversation messages for context
            
        Returns:
            RAGResponse with answer and metadata
        """
        start_time = time.time()
        
        if class_num is None:
            self.logger.info(f"Processing query for ALL CLASSES: {question[:100]}...")
        else:
            self.logger.info(f"Processing query for class{class_num}: {question[:100]}...")
        
        try:
            # Step 1: Validate inputs
            self._validate_inputs(question, class_num)
            
            # Step 2: Check cache
            # Convert conversation history to context string for caching
            conversation_context = ""
            if conversation_history:
                # Format last 5 messages for context
                last_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
                context_parts = []
                for msg in last_messages:
                    try:
                        # Handle both dict and object formats
                        if hasattr(msg, 'role') and hasattr(msg, 'content'):
                            # Object format (ChatMessage)
                            role = "User" if msg.role == "user" else "Assistant"
                            content = msg.content.strip() if msg.content else ""
                        elif isinstance(msg, dict):
                            # Dict format (fallback)
                            role = "User" if msg.get("isUser", True) else "Assistant"
                            content = msg.get("content", "").strip()
                        else:
                            # Skip unknown formats
                            continue
                        
                        if content:  # Only include non-empty messages
                            context_parts.append(f"{role}: {content}")
                    except Exception as e:
                        self.logger.warning(f"Error processing conversation message: {e}")
                        continue
                conversation_context = " | ".join(context_parts)
            
            cache_key = self._generate_cache_key(question, class_num, conversation_context)
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                self.logger.info("Cache hit - returning cached response")
                self._query_stats["cache_hits"] += 1
                self._query_stats["total_queries"] += 1
                return cached_response
            
            # Step 3: Retrieve similar documents - use config values
            top_k = getattr(self.config.rag.retrieval, 'top_k', 3)
            parallel_search = getattr(self.config.rag.retrieval, 'parallel_search', True)
            documents = self._retrieve_documents(question, class_num, n_results=top_k, parallel_search=parallel_search)
            
            # Step 4: Handle empty retrieval - try to answer with LLM anyway
            if not documents:
                class_desc = "all classes" if class_num is None else f"class {class_num}"
                self.logger.warning(f"[RAG] No documents retrieved for {class_desc}")
                self.logger.info(f"[ANSWER_SOURCE] LLM_ONLY (no RAG context found) - attempting to answer using LLM knowledge")
                
                # Try to answer using LLM's built-in knowledge
                try:
                    answer, llm_metadata = self._generate_answer_without_context(question, class_num, conversation_context)
                    llm_metadata['answer_source'] = 'llm_only'
                    llm_metadata['rag_context'] = False
                except Exception as e:
                    self.logger.error(f"Failed to generate answer without context: {e}")
                    answer = "I couldn't find specific information about this topic in the curriculum, and I encountered an error trying to answer from my knowledge base. Please rephrase your question or check if it's related to the correct class level."
                    llm_metadata = {'answer_source': 'error', 'rag_context': False, 'error': str(e)}
            else:
                # Step 5: Generate answer with documents
                self.logger.info(f"[RAG] Retrieved {len(documents)} documents")
                self.logger.info(f"[ANSWER_SOURCE] RAG_CONTEXT (using {len(documents)} retrieved documents)")
                answer, llm_metadata = self._generate_answer(question, documents, class_num, conversation_context)
                llm_metadata['answer_source'] = 'rag_context'
                llm_metadata['rag_context'] = True
            
            # Step 6: Create response
            processing_time = time.time() - start_time
            
            response = RAGResponse(
                answer=answer,
                sources=documents,
                metadata={
                    'processing_time': round(processing_time, 3),
                    'class_num': class_num,
                    'documents_retrieved': len(documents),
                    'timestamp': time.time(),
                    **llm_metadata
                },
                cache_hit=False
            )
            
            # Step 7: Add to cache
            self._add_to_cache(cache_key, response)
            
            # Update statistics
            self._query_stats["total_queries"] += 1
            total_time = self._query_stats["avg_processing_time"] * (self._query_stats["total_queries"] - 1)
            self._query_stats["avg_processing_time"] = (total_time + processing_time) / self._query_stats["total_queries"]
            
            self.logger.info(f"Query processed successfully in {processing_time:.3f}s")
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            
            # Return error response
            return RAGResponse(
                answer=f"I encountered an error processing your question: {str(e)}",
                sources=[],
                metadata={
                    'error': str(e),
                    'processing_time': time.time() - start_time,
                    'class_num': class_num,
                    'timestamp': time.time()
                },
                cache_hit=False
            )
    
    def batch_index_questions(self, class_num: int, questions_file_path: str) -> Dict[str, Any]:
        """
        Bulk import questions from JSON/CSV file with paraphrasing.
        
        Args:
            class_num: Target class number
            questions_file_path: Path to questions file (JSON or CSV)
            
        Returns:
            Dictionary with indexing statistics
        """
        self.logger.info(f"Starting batch indexing for class{class_num} from {questions_file_path}")
        start_time = time.time()
        
        try:
            # Validate inputs
            if not isinstance(class_num, int) or class_num < 1 or class_num > 12:
                raise ValueError("Class number must be between 1 and 12")
            
            file_path = Path(questions_file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Questions file not found: {questions_file_path}")
            
            # Load questions based on file format
            questions = self._load_questions_file(file_path)
            
            if not questions:
                raise ValueError("No questions found in file")
            
            # Process questions in batches
            total_inserted = 0
            total_paraphrases = 0
            batch_size = 10  # Process in smaller batches
            
            for i in range(0, len(questions), batch_size):
                batch = questions[i:i + batch_size]
                batch_start = time.time()
                
                self.logger.info(f"Processing batch {i//batch_size + 1}/{(len(questions)-1)//batch_size + 1}")
                
                for question_data in batch:
                    try:
                        # Extract question text
                        question = self._extract_question_text(question_data)
                        
                        # Generate paraphrases
                        paraphrases = self._generate_paraphrases(question)
                        all_questions = [question] + paraphrases
                        
                        # Insert into database
                        for q in all_questions:
                            self.db_handler.add_question(class_num, q)
                        
                        total_inserted += len(all_questions)
                        total_paraphrases += len(paraphrases)
                        
                    except Exception as e:
                        self.logger.error(f"Error processing question '{question_data}': {e}")
                        continue
                
                batch_time = time.time() - batch_start
                self.logger.debug(f"Batch processed in {batch_time:.2f}s")
            
            total_time = time.time() - start_time
            
            stats = {
                'total_questions_processed': len(questions),
                'total_entries_inserted': total_inserted,
                'total_paraphrases_generated': total_paraphrases,
                'processing_time': round(total_time, 2),
                'questions_per_second': round(len(questions) / total_time, 2),
                'class_num': class_num,
                'source_file': str(file_path)
            }
            
            self.logger.info(f"Batch indexing completed: {stats}")
            return stats
            
        except Exception as e:
            self.logger.error(f"Batch indexing failed: {e}")
            return {
                'error': str(e),
                'processing_time': time.time() - start_time,
                'class_num': class_num,
                'source_file': questions_file_path
            }
    
    def _load_questions_file(self, file_path: Path) -> List[Union[str, Dict[str, Any]]]:
        """Load questions from JSON or CSV file."""
        if file_path.suffix.lower() == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Handle different JSON formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'questions' in data:
                return data['questions']
            else:
                raise ValueError("Invalid JSON format. Expected list or dict with 'questions' key")
                
        elif file_path.suffix.lower() == '.csv':
            questions = []
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    questions.append(row)
            return questions
            
        else:
            raise ValueError("Unsupported file format. Use JSON or CSV")
    
    def _extract_question_text(self, question_data: Union[str, Dict[str, Any]]) -> str:
        """Extract question text from various data formats."""
        if isinstance(question_data, str):
            return question_data.strip()
        elif isinstance(question_data, dict):
            # Try common field names
            for field in ['question', 'text', 'content', 'query']:
                if field in question_data:
                    return str(question_data[field]).strip()
            
            # If no standard field, use first string value
            for value in question_data.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()
            
            raise ValueError(f"No question text found in: {question_data}")
        else:
            return str(question_data).strip()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache and performance statistics."""
        return {
            'cache_size': len(self._cache),
            'max_cache_size': self._max_cache_size,
            'cache_hit_rate': (
                self._query_stats["cache_hits"] / max(1, self._query_stats["total_queries"])
            ) * 100,
            **self._query_stats
        }
    
    def clear_cache(self) -> None:
        """Clear the query cache."""
        self._cache.clear()
        self._cache_order.clear()
        self.logger.info("Query cache cleared")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics for all class collections."""
        stats = {}
        for class_num in range(1, 13):
            try:
                class_stats = self.db_handler.get_collection_stats(class_num)
                stats[f'class{class_num}'] = class_stats
            except Exception as e:
                stats[f'class{class_num}'] = {'error': str(e)}
        
        return stats
    
    def retrieve_documents(self, question: str, class_num: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Public method to retrieve documents without generating answer.
        Used for streaming where we want to show sources first.
        
        Args:
            question: Query question
            class_num: Optional class number filter
            
        Returns:
            List of retrieved documents
        """
        return self._retrieve_documents(
            question=question,
            class_num=class_num,
            n_results=self.config.rag.retrieval.top_k,
            parallel_search=True  # Enable parallel search by default
        )
    
    def generate_answer_stream(
        self,
        question: str,
        sources: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict]] = None
    ):
        """
        Generate answer with streaming support - yields tokens as they're generated.
        
        Args:
            question: The user's question
            sources: Retrieved source documents
            conversation_history: Optional conversation context
            
        Yields:
            Individual tokens/words as they're generated
        """
        try:
            # Format the retrieved context
            retrieved_context = sources if sources else []
            
            # Detect if it's a math/science problem
            use_hybrid = self._is_math_or_science_problem(question)
            
            # Generate answer with streaming
            for token in self.llm_handler.generate_answer_stream(
                question=question,
                retrieved_context=retrieved_context,
                conversation_context=conversation_history,
                use_hybrid_prompt=use_hybrid
            ):
                yield token
                
        except Exception as e:
            self.logger.error(f"Error in streaming answer generation: {e}")
            yield f"Error: {str(e)}"
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        try:
            # Close database connections
            if hasattr(self.db_handler, '__exit__'):
                self.db_handler.__exit__(exc_type, exc_val, exc_tb)
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


# Utility functions for external usage
def create_rag_pipeline(config_path: str = "config.yaml") -> RAGPipeline:
    """
    Factory function to create RAG pipeline with configuration.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configured RAG pipeline instance
    """
    from .config_loader import ConfigLoader
    
    config_loader = ConfigLoader()
    config = config_loader.load_config(config_path)
    
    return RAGPipeline(config)


if __name__ == "__main__":
    # Demo usage
    import sys
    from pathlib import Path
    
    # Add parent directory to path for imports
    sys.path.append(str(Path(__file__).parent.parent))
    
    from src.config_loader import ConfigLoader
    
    # Load configuration
    config_loader = ConfigLoader()
    config = config_loader.load_config("config.yaml")
    
    # Create pipeline
    with RAGPipeline(config) as pipeline:
        print("RAG Pipeline Demo")
        print("=" * 50)
        
        # Example query
        test_question = "What is photosynthesis?"
        test_class = 10
        
        print(f"Processing query: '{test_question}' for Class {test_class}")
        
        response = pipeline.process_query(test_question, test_class)
        
        print(f"\nAnswer: {response.answer}")
        print(f"\nSources found: {len(response.sources)}")
        print(f"Processing time: {response.metadata.get('processing_time', 0):.3f}s")
        
        # Show cache stats
        print(f"\nCache Statistics:")
        stats = pipeline.get_cache_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")