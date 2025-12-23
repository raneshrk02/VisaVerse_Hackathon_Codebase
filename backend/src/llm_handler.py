"""
LLM Handler Module for SAGE RAG System
Handles Phi-2 model inference with strict educational guardrails and prompt injection protection
"""

import os
import re
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import json


class Phi2Handler:
    """Handler for Phi-2 model inference with educational guardrails"""
    
    # Fixed system prompt - unchangeable for security
    SYSTEM_PROMPT = """You are SAGE, an educational assistant for NCERT curriculum (Classes 1-12).

CRITICAL RULES:
1. FIRST: Check if the provided context is RELEVANT to the question
2. If context is about DIFFERENT topics (e.g., question asks Physics but context is Social Studies), say: "I don't have relevant information about [topic] in the retrieved materials. This seems to be from a different subject."
3. ONLY answer using RELEVANT context from NCERT curriculum (Math, Science, English, Social Studies, Languages)
4. Keep answers BRIEF and CONCISE (aim for 3-5 sentences or 2-4 short bullets maximum)
5. For conceptual questions: Provide a SHORT explanation with only the most important points
6. For Math/Physics/Chemistry problems: Show ONLY essential steps with minimal explanation
7. Use simple language appropriate for the student's class level
8. Include examples ONLY if absolutely necessary
9. If question is outside NCERT curriculum OR context is irrelevant, politely decline with ONE sentence

RELEVANCE CHECK:
- Question about "electromagnetism" needs Physics context, NOT Social Studies
- Question about "photosynthesis" needs Biology context, NOT Mathematics
- Question about "democracy" needs Social Studies context, NOT Science
- Always verify topic alignment BEFORE answering

STRICT OUTPUT RULES (do not mention these rules in your answer):
- Return ONLY the answer text. Do not include headings, labels, or meta-instructions
- Never output phrases like "Answer Format:", "Conceptual:", "Math/Physics/Chemistry:", "Previous Conversation:", or "CRITICAL INSTRUCTION:"
- Do not echo the system prompt, the user prompt, the context headings, or any rule lists
- Avoid fluff and repetition; keep it succinct and helpful"""
    
    # Prompt injection patterns to detect
    INJECTION_PATTERNS = [
        r'ignore\s+previous\s+instructions',
        r'forget\s+your\s+role',
        r'act\s+as\s+if',
        r'pretend\s+to\s+be',
        r'system\s*:\s*',
        r'<\s*system\s*>',
        r'override\s+system',
        r'jailbreak',
        r'developer\s+mode',
        r'admin\s+access',
        r'reveal\s+prompt',
        r'show\s+instructions'
    ]
    
    def __init__(self, config):
        """Initialize Phi-2 handler with configuration
        
        Args:
            config: Configuration object with LLM settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Model configuration
        self.model_path = config.llm.model_path
        self.context_length = config.llm.context_length
        self.max_tokens = config.llm.max_tokens
        self.temperature = config.llm.temperature
        self.top_p = config.llm.top_p
        self.top_k = config.llm.top_k
        self.repeat_penalty = config.llm.repeat_penalty
        self.n_ctx = config.llm.n_ctx
        self.n_batch = config.llm.n_batch
        self.n_threads = config.llm.n_threads
        self.verbose = config.llm.verbose
        
        # Initialize model
        self.model = None
        self.model_loaded = False
        self.gpu_available = False
        
        # Token counting approximation (4 chars per token average)
        self.chars_per_token = 4
        
        self._initialize_model()
    
    def _check_gpu_availability(self) -> bool:
        """Check if GPU acceleration is available"""
        try:
            import torch
            if torch.cuda.is_available():
                self.logger.info("CUDA GPU detected")
                return True
        except ImportError:
            pass
        
        # Check for Metal (macOS)
        try:
            import platform
            if platform.system() == "Darwin":
                self.logger.info("macOS detected - Metal acceleration may be available")
                return True
        except Exception:
            pass
        
        self.logger.info("No GPU acceleration detected, using CPU")
        return False
    
    def _initialize_model(self) -> None:
        """Initialize the Phi-2 model with GPU/CPU fallback"""
        try:
            # Import llama-cpp-python
            try:
                from llama_cpp import Llama
                self.logger.info("llama-cpp-python imported successfully")
            except ImportError as e:
                self.logger.error(
                    "llama-cpp-python not found. Please install it with: "
                    "pip install llama-cpp-python"
                )
                raise ImportError(f"llama-cpp-python not available: {e}")
            
            # Check if model file exists
            if not os.path.exists(self.model_path):
                error_msg = (
                    f"Model file not found: {self.model_path}\n"
                    f"Please download the Phi-2 GGUF model and place it at {self.model_path}\n"
                    f"You can download from: https://huggingface.co/microsoft/phi-2-gguf"
                )
                self.logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # Check GPU availability
            self.gpu_available = self._check_gpu_availability()
            
            # Initialize the model
            self.logger.info(f"Loading Phi-2 model from {self.model_path}")
            start_time = time.time()
            
            model_params = {
                'model_path': self.model_path,
                'n_ctx': self.n_ctx,
                'n_batch': self.n_batch,
                'verbose': self.verbose
            }
            
            # Add GPU parameters if available
            if self.gpu_available:
                try:
                    # Try GPU initialization first
                    model_params['n_gpu_layers'] = -1  # Use all GPU layers
                    self.model = Llama(**model_params)
                    self.logger.info("Model loaded with GPU acceleration")
                except Exception as gpu_error:
                    self.logger.warning(f"GPU initialization failed: {gpu_error}")
                    self.logger.info("Falling back to CPU...")
                    # Fallback to CPU
                    model_params.pop('n_gpu_layers', None)
                    self.model = Llama(**model_params)
                    self.gpu_available = False
            else:
                # CPU only
                if self.n_threads > 0:
                    model_params['n_threads'] = self.n_threads
                self.model = Llama(**model_params)
            
            load_time = time.time() - start_time
            acceleration = "GPU" if self.gpu_available else "CPU"
            self.logger.info(f"Phi-2 model loaded successfully in {load_time:.2f}s using {acceleration}")
            self.model_loaded = True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Phi-2 model: {e}")
            self.model_loaded = False
            raise
    
    def _apply_guardrails(self, prompt: str) -> bool:
        """Validate prompt doesn't contain injection attempts
        
        Args:
            prompt: Input prompt to validate
            
        Returns:
            True if prompt is safe, False if injection detected
        """
        prompt_lower = prompt.lower()
        
        # Check for injection patterns
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                self.logger.warning(f"Potential prompt injection detected: {pattern}")
                return False
        
        # Check for excessive system-like tokens
        system_keywords = ['system', 'assistant', 'user', 'admin', 'root', 'override']
        system_count = sum(prompt_lower.count(keyword) for keyword in system_keywords)
        
        if system_count > 3:  # Threshold for suspicious activity
            self.logger.warning(f"Excessive system keywords detected: {system_count}")
            return False
        
        # Check for unusual formatting that might indicate injection
        suspicious_patterns = [
            r'<\s*system\s*>',
            r'\{[^}]*\}',  # Curly braces (potential template injection)
            r'```[^`]*```',  # Code blocks
        ]
        
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            if len(matches) > 2:  # Allow some formatting but not excessive
                self.logger.warning(f"Suspicious formatting detected: {pattern}")
                return False
        
        # NOTE: We do NOT filter based on curriculum keywords here
        # The model will be trained to handle off-topic questions appropriately
        # via the system prompt and context checking
        
        return True
    
    def _check_content_relevance(self, question: str, content: str) -> bool:
        """
        Check if document content is actually relevant to the question using keyword overlap
        
        Args:
            question: User's question
            content: Document content to validate
            
        Returns:
            True if content appears relevant, False otherwise
        """
        # Extract key terms from question (simple keyword extraction)
        question_lower = question.lower()
        content_lower = content.lower()
        
        # Define subject domain keywords
        math_keywords = ['angle', 'triangle', 'trigonometry', 'tan', 'sin', 'cos', 'elevation', 'height', 
                        'distance', 'theorem', 'equation', 'formula', 'calculate', 'solve', 'degree']
        physics_keywords = ['force', 'motion', 'velocity', 'acceleration', 'energy', 'work', 'power',
                          'mass', 'momentum', 'gravity', 'friction', 'electromagnetic', 'wave']
        chemistry_keywords = ['element', 'compound', 'reaction', 'molecule', 'atom', 'bond', 'solution',
                            'acid', 'base', 'oxidation', 'reduction', 'periodic']
        
        # Check which domain the question belongs to
        question_domains = []
        if any(kw in question_lower for kw in math_keywords):
            question_domains.append('math')
        if any(kw in question_lower for kw in physics_keywords):
            question_domains.append('physics')
        if any(kw in question_lower for kw in chemistry_keywords):
            question_domains.append('chemistry')
        
        # If we can't identify domain, allow the document
        if not question_domains:
            return True
        
        # Check if content belongs to the same domain
        content_matches_domain = False
        if 'math' in question_domains:
            content_matches_domain = any(kw in content_lower for kw in math_keywords)
        if 'physics' in question_domains:
            content_matches_domain = content_matches_domain or any(kw in content_lower for kw in physics_keywords)
        if 'chemistry' in question_domains:
            content_matches_domain = content_matches_domain or any(kw in content_lower for kw in chemistry_keywords)
        
        return content_matches_domain
    
    def _format_context(self, retrieved_docs: List[Dict[str, Any]], question: str = "") -> str:
        """Format retrieved documents for LLM input with aggressive relevance filtering
        
        Args:
            retrieved_docs: List of retrieved documents with content and metadata
            question: Original question (for keyword-based relevance checking)
            
        Returns:
            Formatted context string
        """
        if not retrieved_docs:
            return "No curriculum documents found. Solve this problem using standard mathematical/scientific principles and methods."
        
        context_parts = []
        
        # MUCH stricter similarity threshold - only include highly relevant documents
        MIN_SIMILARITY = 0.75  # Increased to 75% for better quality
        filtered_docs = [doc for doc in retrieved_docs if doc.get('similarity_score', 0.0) >= MIN_SIMILARITY]
        
        # Additional keyword-based relevance filter
        if question:
            keyword_filtered = []
            for doc in filtered_docs:
                content = doc.get('content', '')
                if self._check_content_relevance(question, content):
                    keyword_filtered.append(doc)
                else:
                    self.logger.info(f"Filtered out document due to keyword mismatch (similarity: {doc.get('similarity_score', 0):.2f})")
            filtered_docs = keyword_filtered
        
        if not filtered_docs:
            self.logger.warning(f"All {len(retrieved_docs)} retrieved documents were filtered out (similarity or keyword mismatch)")
            return f"No sufficiently relevant information found in the curriculum materials for this question. Please solve using standard NCERT formulas and concepts."
        
        if len(filtered_docs) < len(retrieved_docs):
            self.logger.info(f"Filtered out {len(retrieved_docs) - len(filtered_docs)} low-relevance documents (similarity < {MIN_SIMILARITY} or keyword mismatch)")
        
        for i, doc in enumerate(filtered_docs, 1):
            content = doc.get('content', '').strip()
            metadata = doc.get('metadata', {})
            similarity_score = doc.get('similarity_score', 0.0)
            
            # Create document header
            header_parts = [f"Reference {i}"]
            
            # Add class information if available
            class_info = None
            if 'class_num' in metadata:
                class_info = f"Class {metadata['class_num']}"
            elif 'class' in metadata:
                class_info = metadata['class']
            
            if class_info:
                header_parts.append(class_info)
            
            # Add subject if available
            if 'subject' in metadata:
                header_parts.append(f"Subject: {metadata['subject']}")
            
            # Add similarity score for transparency
            header_parts.append(f"Relevance: {similarity_score:.2f}")
            
            header = " | ".join(header_parts)
            
            # Format the document
            formatted_doc = f"[{header}]\n{content}\n"
            context_parts.append(formatted_doc)
        
        return "\n".join(context_parts)
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate number of tokens in text
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return len(text) // self.chars_per_token
    
    def _create_prompt(self, question: str, context: str, prompt_type: str = "answer", conversation_context: str = "") -> str:
        """Create a properly formatted prompt
        
        Args:
            question: User's question
            context: Retrieved context
            prompt_type: Type of prompt ("answer", "paraphrase", or "hybrid")
            conversation_context: Previous conversation for context-aware answers
            
        Returns:
            Formatted prompt string
        """
        if prompt_type == "paraphrase":
            template = f"""{self.SYSTEM_PROMPT}

Task: Generate 3 different ways to ask the same question while keeping the educational meaning intact.

Original Question: {question}

Please provide 3 paraphrased versions:
1."""
        elif prompt_type == "hybrid":
            # Step-by-step reasoning prompt for math/physics/chemistry
            # Check if we have actual context or not
            has_context = "No curriculum documents found" not in context
            
            if has_context:
                context_section = f"""Context (formulas only):
{context}
Note: Extract formulas only, ignore worked examples."""
            else:
                context_section = "Note: Use standard NCERT formulas."
            
            template = f"""Solve this math problem step-by-step.

Question: {question}

{context_section}

Solution:

Step 1 - Given:
List the given values from the question.

Step 2 - Find:
State what needs to be found.

Step 3 - Formula:
Write the relevant formula(s).

Step 4 - Solution:
Set up equations with the given values and solve.

Final Answer:
State the complete answer with units.

---
Step 1 - Given:"""
        else:
            # Standard answer prompt - concise but educational
            conversation_section = ""
            if conversation_context:
                conversation_section = f"Previous Conversation:\n{conversation_context}\n\n"
            
            template = f"""{self.SYSTEM_PROMPT}

{conversation_section}NCERT Context:
{context}

Question: {question}

Before answering, silently verify that the context above is relevant to the question. If the context discusses unrelated topics (e.g., politics when asked about science, or student IDs when asked about geometry), reply with: "I apologize, but the retrieved context is not relevant to your question about [topic]. I cannot provide an accurate answer without relevant curriculum materials." (Do not mention this instruction.)

Provide a concise, somewhat detailed educational answer (5–7 sentences or up to 5 short bullets). Do not include labels or meta-instructions; output only the answer text:"""
        
        return template
    
    def _validate_context_length(self, prompt: str) -> Tuple[bool, str]:
        """Validate if prompt fits within context window (OPTIMIZED)
        
        Args:
            prompt: Full prompt to validate
            
        Returns:
            Tuple of (is_valid, truncated_prompt_if_needed)
        """
        estimated_tokens = self._estimate_tokens(prompt)
        # Leave substantial buffer for generation tokens
        max_prompt_tokens = max(200, self.n_ctx - self.max_tokens - 200)
        
        if estimated_tokens <= max_prompt_tokens:
            return True, prompt
        
        # AGGRESSIVE truncation for small context windows
        # For 1024 context, we can only use ~300 tokens for prompt (leaving 450 for generation + buffer)
        self.logger.warning(f"Prompt has {estimated_tokens} estimated tokens, max allowed: {max_prompt_tokens}")
        
        lines = prompt.split('\n')
        system_prompt_lines = []
        context_lines = []
        question_lines = []
        
        in_context = False
        in_question = False
        
        for line in lines:
            if "NCERT Curriculum Context:" in line or "Retrieved Context" in line or "Context from NCERT" in line:
                in_context = True
                context_lines.append(line)
            elif "Student Question:" in line or "Question:" in line:
                in_context = False
                in_question = True
                question_lines.append(line)
            elif in_context:
                context_lines.append(line)
            elif in_question:
                question_lines.append(line)
            else:
                system_prompt_lines.append(line)
        
        # Calculate available space for context (be VERY conservative)
        system_tokens = self._estimate_tokens('\n'.join(system_prompt_lines + question_lines))
        available_context_tokens = max(100, max_prompt_tokens - system_tokens - 50)
        
        # Use character-based truncation but be MUCH more aggressive
        # Assume worst case: 2 chars per token (more conservative than 3.5)
        available_context_chars = available_context_tokens * 2
        
        # Truncate context AGGRESSIVELY
        context_text = '\n'.join(context_lines)
        if len(context_text) > available_context_chars:
            # Take only first portion with large safety margin
            context_text = context_text[:int(available_context_chars * 0.6)]  # Only 60% of estimated space
            context_text += "\n[Content truncated due to length...]"
            context_lines = context_text.split('\n')
        
        truncated_prompt = '\n'.join(system_prompt_lines + context_lines + question_lines)
        
        self.logger.warning(f"Prompt truncated from {estimated_tokens} to ~{self._estimate_tokens(truncated_prompt)} tokens (max allowed: {max_prompt_tokens})")
        return False, truncated_prompt
    
    def generate_paraphrases(self, question: str, num_variations: int = 3) -> List[str]:
        """Generate paraphrased versions of input question
        
        Args:
            question: Original question
            num_variations: Number of variations to generate (fixed at 3)
            
        Returns:
            List of paraphrased questions
        """
        if not self.model_loaded:
            self.logger.error("Model not loaded, cannot generate paraphrases")
            return [question]  # Return original as fallback
        
        # Apply guardrails
        if not self._apply_guardrails(question):
            self.logger.warning("Question failed guardrail check, returning original")
            return [question]
        
        try:
            # Create paraphrase prompt
            prompt = self._create_prompt(question, "", "paraphrase")
            
            # Validate prompt length
            is_valid, final_prompt = self._validate_context_length(prompt)
            
            self.logger.info(f"Generating paraphrases for: {question[:50]}...")
            start_time = time.time()
            
            try:
                # Generate paraphrases with error handling
                response = self.model(
                    final_prompt,
                    max_tokens=150,  # Reduced from 200 for stability
                    temperature=0.7,  # Reduced from 0.8 for stability
                    top_p=self.top_p,
                    top_k=self.top_k,
                    repeat_penalty=self.repeat_penalty,
                    stop=['\n\n', '4.', 'Original Question:', 'Task:'],
                    echo=False
                )
                
                generation_time = time.time() - start_time
                generated_text = response['choices'][0]['text'].strip()
                
                # Parse paraphrases
                paraphrases = self._parse_paraphrases(generated_text, question)
                
                self.logger.info(f"Generated {len(paraphrases)} paraphrases in {generation_time:.2f}s")
                self.logger.debug(f"Paraphrases: {paraphrases}")
                
                return paraphrases
            except RuntimeError as model_err:
                # Handle llama_decode and GGML errors
                if "llama_decode returned" in str(model_err) or "GGML_ASSERT" in str(model_err):
                    self.logger.warning(f"Model runtime error during paraphrasing (will skip): {model_err}")
                    return [question]  # Skip paraphrasing and return original
                raise
            
        except Exception as e:
            self.logger.error(f"Failed to generate paraphrases: {e}")
            return [question]  # Return original as fallback
    
    def _parse_paraphrases(self, generated_text: str, original_question: str) -> List[str]:
        """Parse generated paraphrases from model output
        
        Args:
            generated_text: Raw model output
            original_question: Original question for fallback
            
        Returns:
            List of parsed paraphrases
        """
        paraphrases = []
        
        # Look for numbered variations
        lines = generated_text.split('\n')
        
        for line in lines:
            line = line.strip()
            # Match patterns like "1. question", "2. question", etc.
            match = re.match(r'^[1-3]\.\s*(.+)', line)
            if match:
                paraphrase = match.group(1).strip()
                if paraphrase and paraphrase != original_question:
                    paraphrases.append(paraphrase)
        
        # If we don't have 3 paraphrases, pad with variations
        while len(paraphrases) < 3:
            if len(paraphrases) == 0:
                paraphrases.append(original_question)
            elif len(paraphrases) == 1:
                paraphrases.append(f"Can you explain {original_question.lower()}")
            else:
                paraphrases.append(f"What do you know about {original_question.lower()}")
        
        return paraphrases[:3]  # Ensure exactly 3 paraphrases
    
    def generate_answer(self, question: str, retrieved_context: List[Dict[str, Any]], conversation_context: str = "", use_hybrid_prompt: bool = False) -> str:
        """Combine context and generate final answer (with hybrid mode support)
        
        Args:
            question: User's question
            retrieved_context: List of retrieved documents
            conversation_context: Previous conversation context for better answers
            use_hybrid_prompt: Use step-by-step reasoning prompt for math/physics/chemistry
            
        Returns:
            Generated educational answer
        """
        if not self.model_loaded:
            error_msg = ("I apologize, but the educational assistant is currently unavailable. "
                        "Please try again later or contact support.")
            self.logger.error("Model not loaded, cannot generate answer")
            return error_msg
        
        # Apply guardrails to question
        if not self._apply_guardrails(question):
            return ("I can only help with educational questions about NCERT curriculum. "
                   "Please ask about subjects like Mathematics, Science, English, Social Studies, etc.")
        
        try:
            # Format context with keyword-based relevance filtering
            formatted_context = self._format_context(retrieved_context, question)
            
            # Create prompt with conversation context (use hybrid prompt if requested)
            prompt_type = "hybrid" if use_hybrid_prompt else "answer"
            prompt = self._create_prompt(question, formatted_context, prompt_type, conversation_context)
            
            # Validate context length
            is_valid, final_prompt = self._validate_context_length(prompt)
            if not is_valid:
                self.logger.warning("Prompt was truncated due to length constraints")
            
            self.logger.info(f"Generating answer for: {question[:50]}...")
            self.logger.debug(f"Prompt length: {len(final_prompt)} chars")
            start_time = time.time()
            
            try:
                response = self.model(
                    final_prompt,
                    max_tokens=self.max_tokens,  # Configurable answer length
                    temperature=0.2,  # Lower for focused output
                    top_p=0.9,  
                    top_k=40,
                    repeat_penalty=1.15,  
                    stop=['Student Question:', 'Question:', 'Context:', 'Answer Format:', 'Conceptual:', 'Previous Conversation:', '\n\n\n\n'],
                    echo=False
                )
                
                generation_time = time.time() - start_time
                generated_answer = response['choices'][0]['text'].strip()
                
                # Post-process answer
                final_answer = self._post_process_answer(generated_answer, question, retrieved_context)
                
                self.logger.info(f"Answer generated in {generation_time:.2f}s")
                self.logger.debug(f"Generated answer: {final_answer[:100]}...")
                
                # Log the interaction for debugging
                self._log_interaction(question, retrieved_context, final_answer)
                
                return final_answer
            
            except RuntimeError as model_err:
                # Handle llama_decode and GGML errors gracefully
                error_msg = str(model_err)
                self.logger.error(f"Model computation error: {error_msg}")
                if "llama_decode returned" in error_msg or "GGML_ASSERT" in error_msg:
                    # Return a helpful message with context from documents
                    if retrieved_context:
                        self.logger.info("Falling back to simple answer generation")
                        return self._generate_simple_answer(question, retrieved_context)
                    return ("I encountered a processing error while generating an answer. "
                           "Please try asking a simpler question or reformulate your query.")
                raise
            except Exception as gen_err:
                # Catch any other generation errors
                self.logger.error(f"Generation error: {gen_err}", exc_info=True)
                if retrieved_context:
                    self.logger.info("Falling back to simple answer generation")
                    return self._generate_simple_answer(question, retrieved_context)
                return ("I encountered an error during generation. Please try rephrasing your question.")
                
        except Exception as e:
            self.logger.error(f"Failed to generate answer: {e}")
            return ("I apologize, but I encountered an error while processing your question. "
                   "Please try rephrasing your question or ask about a different topic.")
    
    def generate_answer_without_context(self, question: str, class_num: Optional[int] = None, 
                                       conversation_context: str = "", use_step_by_step: bool = False) -> str:
        """Generate answer using only LLM's built-in knowledge (no RAG context).
        
        Args:
            question: User's question
            class_num: Class number for educational level context
            conversation_context: Previous conversation context
            use_step_by_step: Use step-by-step reasoning for math/science problems
            
        Returns:
            Generated answer using LLM knowledge
        """
        if not self.model_loaded:
            error_msg = ("I apologize, but the educational assistant is currently unavailable. "
                        "Please try again later or contact support.")
            self.logger.error("Model not loaded, cannot generate answer")
            return error_msg
        
        # Apply guardrails
        if not self._apply_guardrails(question):
            return ("I can only help with educational questions about NCERT curriculum. "
                   "Please ask about subjects like Mathematics, Science, English, Social Studies, etc.")
        
        try:
            # Create a special prompt for answering without context
            class_context = f" for Class {class_num}" if class_num else ""
            
            if use_step_by_step:
                # For math/science problems, use step-by-step reasoning
                prompt_template = f"""You are SAGE, an educational assistant{class_context}.

Solve this math/science problem with a complete step-by-step solution. Show all work and explain your reasoning.

Question: {question}

Solution:
Step 1:"""
            else:
                # For conceptual questions - detailed explanation
                prompt_template = f"""You are SAGE, an educational assistant{class_context}.

Provide a clear and detailed explanation for this question. Include examples and context where helpful.

{conversation_context}

Question: {question}

Answer:"""
            
            self.logger.info(f"Generating answer without RAG context (step-by-step: {use_step_by_step})")
            start_time = time.time()
            
            try:
                # Generate answer - use configured max_tokens
                max_tokens = self.max_tokens if use_step_by_step else max(150, self.max_tokens - 50)  # Slightly shorter for conceptual
                
                response = self.model(
                    prompt_template,
                    max_tokens=max_tokens,
                    temperature=0.4,  # Slightly higher for natural explanations
                    top_p=0.85,  # Increased for more variety
                    top_k=30,  # Increased for better word choices
                    repeat_penalty=1.15,  # Slightly lower for natural flow
                    stop=['Question:', 'Student:'],  # Removed \n\n\n
                    echo=False
                )
                
                generation_time = time.time() - start_time
                generated_answer = response['choices'][0]['text'].strip()
                
                # Post-process
                final_answer = self._post_process_answer(generated_answer, question, [])
                
                self.logger.info(f"Answer generated without context in {generation_time:.2f}s")
                
                return final_answer
                
            except RuntimeError as model_err:
                if "llama_decode returned" in str(model_err) or "GGML_ASSERT" in str(model_err):
                    self.logger.error(f"Model computation error: {model_err}")
                    return ("I encountered a processing error. Please try simplifying your question or "
                           "breaking it into smaller parts.")
                raise
            except Exception as gen_err:
                self.logger.error(f"Generation error in without_context: {gen_err}")
                return ("I encountered an error. Please try rephrasing your question in simpler terms.")
                
        except Exception as e:
            self.logger.error(f"Failed to generate answer without context: {e}")
            return ("I apologize, but I encountered an error while processing your question. "
                   "Please try rephrasing your question.")
    
    def generate_answer_stream(
        self,
        question: str,
        retrieved_context: List[Dict[str, Any]],
        conversation_context: str = "",
        use_hybrid_prompt: bool = False
    ):
        """
        Generate answer with streaming support - yields tokens as they're generated.
        
        Args:
            question: User's question
            retrieved_context: List of retrieved documents
            conversation_context: Previous conversation context
            use_hybrid_prompt: Use step-by-step reasoning for math/science
            
        Yields:
            Individual tokens/words as they're generated by the model
        """
        if not self.model_loaded:
            yield "I apologize, but the educational assistant is currently unavailable."
            return
        
        # Apply guardrails
        if not self._apply_guardrails(question):
            yield "I can only help with educational questions about NCERT curriculum."
            return
        
        try:
            # Format context with keyword-based relevance filtering
            formatted_context = self._format_context(retrieved_context, question)
            
            # Create prompt
            prompt_type = "hybrid" if use_hybrid_prompt else "answer"
            prompt = self._create_prompt(question, formatted_context, prompt_type, conversation_context)
            
            # Validate context length
            is_valid, final_prompt = self._validate_context_length(prompt)
            if not is_valid:
                self.logger.warning("Prompt was truncated due to length constraints")
            
            # Double-check: if still too long, truncate even more aggressively
            estimated_final_tokens = self._estimate_tokens(final_prompt)
            max_safe_tokens = self.n_ctx - self.max_tokens - 100
            if estimated_final_tokens > max_safe_tokens:
                self.logger.warning(f"Prompt still too long ({estimated_final_tokens} tokens), applying emergency truncation")
                # Emergency truncation: keep only question and minimal context
                lines = final_prompt.split('\n')
                question_section = []
                for line in lines[-10:]:  # Keep only last 10 lines (question area)
                    question_section.append(line)
                final_prompt = "You are SAGE, an educational assistant.\n\n" + '\n'.join(question_section)
            
            self.logger.info(f"Streaming answer for: {question[:50]}...")
            
            try:
                # Generate with streaming enabled - use configured max_tokens
                response_stream = self.model(
                    final_prompt,
                    max_tokens=self.max_tokens,  # Use configured value for consistency
                    temperature=0.2,  # Lower for more focused, deterministic output
                    top_p=0.9,
                    top_k=40,
                    repeat_penalty=1.15,
                    stop=[
                        'Question:', 'Student Question:', 'Context:', 'Answer Format:', 'Conceptual:', 'Previous Conversation:', '\n\n\n\n'
                    ],
                    echo=False,
                    stream=True  # Enable streaming
                )
                
                # Stream tokens one by one
                for chunk in response_stream:
                    if 'choices' in chunk and len(chunk['choices']) > 0:
                        token = chunk['choices'][0].get('text', '')
                        if token:
                            yield token
                
            except RuntimeError as model_err:
                error_msg = str(model_err)
                self.logger.error(f"Model computation error: {error_msg}")
                if "llama_decode returned" in error_msg or "GGML_ASSERT" in error_msg:
                    yield "I encountered a processing error. Please try asking a simpler question."
                    return
                raise
            except Exception as gen_err:
                self.logger.error(f"Generation error: {gen_err}", exc_info=True)
                yield "I encountered an error during generation. Please try rephrasing your question."
                return
                
        except Exception as e:
            self.logger.error(f"Failed to generate streaming answer: {e}")
            yield "I apologize, but I encountered an error while processing your question."
    
    def _post_process_answer(self, answer: str, question: str, context: List[Dict[str, Any]]) -> str:
        """Post-process the generated answer for quality and safety
        
        Args:
            answer: Generated answer
            question: Original question
            context: Retrieved context
            
        Returns:
            Post-processed answer
        """
        # Clean up the answer
        answer = answer.strip()
        
        # Remove any prompt artifacts and system instructions that leaked
        artifacts = [
            'Educational Answer:', 'Answer:', 'Response:', 'Based on the context:',
            'According to the NCERT materials:', 'From the curriculum:', 'Your Response:',
            'IMPORTANT RULES:', 'NOTE:', 'You MUST inform', 'Answer Format:', 'Conceptual:',
            'Math/Physics/Chemistry:', 'Previous Conversation:', 'CRITICAL INSTRUCTION:', 'NCERT Context:'
        ]
        
        for artifact in artifacts:
            if answer.startswith(artifact):
                answer = answer[len(artifact):].strip()

        # Additionally, drop any leading lines that are meta-instructions
        cleaned_lines = []
        for line in answer.split('\n'):
            stripped = line.strip()
            if any(stripped.startswith(a) for a in artifacts):
                continue
            # Drop UI artifacts often injected by clients
            if stripped in ('NCERT', 'View Sources', 'View Sources (5)'):
                continue
            cleaned_lines.append(line)
        answer = '\n'.join(cleaned_lines).strip()
        
        # Check if answer contains leaked system prompt instructions
        leaked_instructions = [
            'ONLY answer questions',
            'IMPORTANT RULES',
            'If the question is NOT',
            'When no relevant context',
            'Do NOT make up',
            'You MUST inform'
        ]
        
        for instruction in leaked_instructions:
            if instruction.lower() in answer.lower():
                # System prompt leaked - return a proper response instead
                return ("I'm here to help with NCERT curriculum questions (Classes 1-12) such as:\n"
                       "- Mathematics concepts and problems\n"
                       "- Science topics and experiments\n"
                       "- English language and literature\n"
                       "- Social Studies and history\n\n"
                       "Please ask me a question about your coursework!")
        
        # Check if answer is too short or generic
        if len(answer) < 20:
            return "I don't have enough information about this topic in the NCERT curriculum materials. Please try asking about a different topic from the curriculum."
        
        # Check for refusal patterns (good - model following instructions)
        refusal_patterns = [
            "I don't have information",
            "not in the curriculum",
            "not covered in",
            "cannot provide information",
            "outside my knowledge",
            "outside the curriculum",
            "not part of ncert"
        ]
        
        # If model properly refuses, that's good
        for pattern in refusal_patterns:
            if pattern.lower() in answer.lower():
                return answer  # Return as-is, model is following guidelines
        
        # Check for confidence and relevance
        # If context has very low similarity scores, the model should acknowledge this
        if context:
            avg_relevance = sum(doc.get('similarity_score', 0) for doc in context) / len(context)
            
            # If average relevance is very low (< 0.3), add a disclaimer
            if avg_relevance < 0.3 and not any(pattern in answer.lower() for pattern in refusal_patterns):
                answer += f"\n\nNote: This answer is based on limited relevant materials. For a more detailed explanation, please refer to your textbook or ask your teacher."
        
        # Add educational context if helpful
        if context and len(answer) > 50:
            # Check if we should add source information
            class_nums = set()
            subjects = set()
            
            for doc in context[:3]:  # Top 3 sources
                metadata = doc.get('metadata', {})
                if 'class_num' in metadata:
                    class_nums.add(str(metadata['class_num']))
                if 'subject' in metadata:
                    subjects.add(metadata['subject'])
            
            source_info = []
            if class_nums:
                if len(class_nums) == 1:
                    source_info.append(f"Class {list(class_nums)[0]}")
                else:
                    source_info.append(f"Classes {', '.join(sorted(class_nums))}")
            
            if subjects:
                source_info.append(f"{', '.join(subjects)}")
            
            if source_info and not any(pattern in answer.lower() for pattern in ['class', 'ncert', 'curriculum', 'textbook']):
                answer += f"\n\n(Source: NCERT {' '.join(source_info)})"
        
        return answer
    
    def _generate_simple_answer(self, question: str, context: List[Dict[str, Any]]) -> str:
        """Generate a simple answer from retrieved context using minimal model inference
        
        Args:
            question: User's question
            context: Retrieved documents
            
        Returns:
            Simple answer constructed from context
        """
        if not context:
            return "I don't have information about this topic in the curriculum materials."
        
        # Format the context concisely
        context_text = "\n\n".join([
            f"[Source {i+1}]: {doc.get('content', '')[:300]}"
            for i, doc in enumerate(context[:3])
        ])
        
        # Create a very simple prompt
        simple_prompt = f"""Based on this curriculum information, answer the question briefly:

{context_text}

Question: {question}

Answer:"""
        
        try:
            # Try minimal generation with conservative settings
            response = self.model(
                simple_prompt,
                max_tokens=160,  # Shorter for concise answers
                temperature=0.3,  # Very focused
                top_p=0.8,
                top_k=20,
                repeat_penalty=1.2,
                stop=['\n\n', 'Question:', 'Source', 'Answer Format:', 'Conceptual:', 'Previous Conversation:'],
                echo=False
            )
            
            answer = response['choices'][0]['text'].strip()
            if answer and len(answer) > 20:  # Valid answer
                return answer
                
        except Exception as e:
            self.logger.error(f"Simple generation failed: {e}")
        
        # If even simple generation fails, extract and format from documents
        response_parts = ["Based on the NCERT curriculum:\n\n"]
        
        for i, doc in enumerate(context[:2], 1):
            content = doc.get('content', '').strip()
            metadata = doc.get('metadata', {})
            
            if content:
                # Clean up the content
                content = content.replace('|', '').replace('  ', ' ').strip()
                
                # Take first complete sentence or 200 chars
                if len(content) > 200:
                    # Try to end at sentence
                    end_pos = content.find('. ', 150)
                    if end_pos > 0:
                        content = content[:end_pos + 1]
                    else:
                        content = content[:200] + "..."
                
                response_parts.append(f"• {content}")
                
                class_num = metadata.get('class_num', '')
                if class_num:
                    response_parts.append(f" (Class {class_num})")
                response_parts.append("\n\n")
        
        return "".join(response_parts).strip()
    
    def _log_interaction(self, question: str, context: List[Dict[str, Any]], answer: str) -> None:
        """Log LLM interaction for debugging
        
        Args:
            question: User question
            context: Retrieved context
            answer: Generated answer
        """
        try:
            interaction_log = {
                'timestamp': time.time(),
                'question': question,
                'context_count': len(context),
                'context_sources': [doc.get('metadata', {}).get('class_num') for doc in context],
                'answer_length': len(answer),
                'model_info': {
                    'temperature': self.temperature,
                    'max_tokens': self.max_tokens,
                    'gpu_used': self.gpu_available
                }
            }
            
            self.logger.debug(f"LLM Interaction: {json.dumps(interaction_log, indent=2)}")
            
        except Exception as e:
            self.logger.warning(f"Failed to log interaction: {e}")
    
    def is_model_loaded(self) -> bool:
        """Check if the model is loaded and ready"""
        return self.model_loaded and self.model is not None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        return {
            'model_path': self.model_path,
            'model_loaded': self.model_loaded,
            'gpu_available': self.gpu_available,
            'context_length': self.context_length,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'system_prompt_active': bool(self.SYSTEM_PROMPT)
        }
    
    def update_generation_params(self, **kwargs) -> None:
        """Update generation parameters
        
        Args:
            **kwargs: Parameters to update (temperature, top_p, top_k, etc.)
        """
        for param, value in kwargs.items():
            if param in ['temperature', 'top_p', 'top_k', 'repeat_penalty', 'max_tokens']:
                old_value = getattr(self, param)
                setattr(self, param, value)
                self.logger.info(f"Updated {param} from {old_value} to {value}")
            else:
                self.logger.warning(f"Unknown parameter: {param}")
    
    def unload_model(self) -> None:
        """Unload the model to free memory"""
        try:
            if self.model:
                del self.model
                self.model = None
                self.model_loaded = False
                self.logger.info("Model unloaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to unload model: {e}")
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            self.unload_model()
        except Exception:
            pass  # Ignore errors during cleanup