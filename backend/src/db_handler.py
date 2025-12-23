"""
Brief: ChromaDB handler that initializes with portable, USB-aware paths.

Uses configuration values that resolve to ../data/ncert_chromadb by default when on USB.
"""

import os
import logging
import hashlib
import uuid
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
from contextlib import contextmanager

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from chromadb.api.models.Collection import Collection


class ChromaDBHandler:
    """Handler for ChromaDB operations with class-based collections (class1-class12)"""
    
    def __init__(self, config):
        """Initialize ChromaDB handler with configuration
        
        Args:
            config: Configuration object with ChromaDB settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # ChromaDB settings
        # Ensure persist directory is portable and absolute
        self.persist_directory = self._resolve_persist_path(config.chromadb.persist_directory)
        self.embedding_model = config.chromadb.embedding_function
        self.chunk_size = config.chromadb.chunk_size
        self.chunk_overlap = config.chromadb.chunk_overlap
        self.read_only = False
        
        # Collection configurations
        self.collections_config = {
            col.name: col.description 
            for col in config.chromadb.collections
        }
        
        # Validate class collections
        self._validate_class_collections()
        
        # Ensure persist directory exists and determine writability
        os.makedirs(self.persist_directory, exist_ok=True)
        self.read_only = not self._check_dir_writable(self.persist_directory)
        if self.read_only:
            self.logger.warning(
                f"ChromaDB persist directory is not writable, enabling read-only mode: {self.persist_directory}"
            )
        
        # Initialize ChromaDB client and collections
        self.client = None
        self.embedding_function = None
        self.collections = {}
        
        self._initialize_client()
        # Verify database integrity and attempt recovery if needed
        self._integrity_verify_and_recover()
        self._initialize_collections()
    
    
    def _validate_class_collections(self) -> None:
        """Validate that all required class collections (class1-class12) are configured"""
        required_classes = [f"class{i}" for i in range(1, 13)]
        configured_classes = list(self.collections_config.keys())
        
        missing_classes = set(required_classes) - set(configured_classes)
        if missing_classes:
            self.logger.warning(f"Missing class collections: {missing_classes}")
            # Add missing classes with default descriptions
            for class_name in missing_classes:
                class_num = class_name.replace('class', '')
                self.collections_config[class_name] = f"Class {class_num} NCERT content"
        
        self.logger.info(f"Validated {len(self.collections_config)} class collections")
    
    def _validate_class_num(self, class_num: int) -> str:
        """Validate class number and return collection name
        
        Args:
            class_num: Class number (1-12)
            
        Returns:
            Collection name (e.g., 'class1')
            
        Raises:
            ValueError: If class_num is not between 1-12
        """
        if not isinstance(class_num, int) or not (1 <= class_num <= 12):
            raise ValueError(f"class_num must be an integer between 1 and 12, got: {class_num}")
        
        collection_name = f"class{class_num}"
        if collection_name not in self.collections_config:
            raise ValueError(f"Collection {collection_name} not configured")
        
        return collection_name
    
    def _initialize_client(self) -> None:
        """Initialize ChromaDB client with persistence and optimizations, honoring read-only state"""
        try:
            # Try with optimizations first
            try:
                self.client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True,
                        # Performance optimizations (may not be supported in all versions)
                        chroma_db_impl="duckdb+parquet",  # Faster than default SQLite
                    )
                )
                self.logger.info(f"ChromaDB client initialized with optimizations at {self.persist_directory}")
            except Exception as opt_error:
                # Fallback to basic settings if optimizations not supported
                self.logger.warning(f"Advanced ChromaDB settings not supported: {opt_error}")
                self.logger.info("Using default ChromaDB settings...")
                self.client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                self.logger.info(f"ChromaDB client initialized at {self.persist_directory}")
        except Exception as e:
            self.logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise

    def _resolve_persist_path(self, configured_path: str) -> str:
        """Resolve configured path to an absolute, USB-aware path.

        Priority:
        - Absolute path as-is
        - If starts with ../data or ./data → resolve relative to detected USB root
        - Otherwise, resolve relative to this module's parent directory
        """
        try:
            p = Path(configured_path)
            if p.is_absolute():
                return str(p)

            # Try USB root from env
            usb_root_env = os.getenv("USB_ROOT")
            if usb_root_env and (configured_path.startswith("../data/") or configured_path.startswith("./data/")):
                usb_root = Path(usb_root_env).expanduser().resolve()
                return str((usb_root / configured_path.replace("./", "").replace("../", "")).resolve())

            # Default: resolve relative to project/app directory
            here = Path(__file__).resolve()
            app_dir = here.parents[2] if len(here.parents) >= 3 else here.parent
            return str((app_dir / configured_path).resolve())
        except Exception:
            return configured_path

    def _check_dir_writable(self, directory: str) -> bool:
        """Return True if the directory is writable (create/delete a temp file)."""
        try:
            test_path = Path(directory) / ".write_test"
            with open(test_path, "w", encoding="utf-8") as f:
                f.write("ok")
            try:
                test_path.unlink()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _integrity_verify_and_recover(self) -> None:
        """Verify ChromaDB integrity and attempt recovery if needed."""
        try:
            # Basic liveness check: list collections
            _ = self.client.list_collections()  # type: ignore[attr-defined]

            # If writable, try a temp collection write/delete
            if not self.read_only:
                temp_name = "_integrity_temp_collection"
                try:
                    tmp = self.client.get_or_create_collection(name=temp_name)  # type: ignore[attr-defined]
                    self.client.delete_collection(name=temp_name)  # type: ignore[attr-defined]
                except Exception as werr:
                    self.logger.warning(f"Write test failed, switching to read-only: {werr}")
                    self.read_only = True
            self.logger.info("ChromaDB integrity check passed")
        except Exception as verr:
            self.logger.error(f"ChromaDB integrity verification failed: {verr}")
            # Attempt recovery: backup and re-init
            try:
                backup_dir = self._backup_database_dir(reason="integrity_failure")
                if backup_dir:
                    self.logger.warning(f"Backed up DB to: {backup_dir}")
                os.makedirs(self.persist_directory, exist_ok=True)
                self._initialize_client()
            except Exception as rec_err:
                self.logger.error(f"ChromaDB recovery failed: {rec_err}")
                raise

    def _backup_database_dir(self, reason: str = "manual") -> str:
        """Create a timestamped backup of the ChromaDB directory and return backup path."""
        src = Path(self.persist_directory)
        if not src.exists():
            return ""
        from datetime import datetime
        import shutil
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = src.parent / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_dir = backup_root / f"chromadb-backup-{ts}-{reason}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, backup_dir / src.name, dirs_exist_ok=True)
        return str(backup_dir)
    
    def _initialize_embedding_function(self) -> None:
        """Initialize sentence-transformers embedding function with local cache support"""
        try:
            import os
            
            # Set local cache directory for offline support
            embeddings_cache = Path(__file__).parent.parent / "embeddings"
            embeddings_cache.mkdir(parents=True, exist_ok=True)
            
            # Set environment variables to use local cache and force offline mode
            os.environ['HF_HOME'] = str(embeddings_cache)
            os.environ['SENTENCE_TRANSFORMERS_HOME'] = str(embeddings_cache)
            os.environ['TRANSFORMERS_CACHE'] = str(embeddings_cache)  # Keep for backwards compatibility
            os.environ['HF_HUB_OFFLINE'] = '1'  # Force offline mode - no internet requests
            os.environ['TRANSFORMERS_OFFLINE'] = '1'  # Additional offline flag
            
            self.logger.info(f"Using embedding cache directory: {embeddings_cache}")
            self.logger.info("Offline mode enabled - will use cached models only")
            
            # Initialize embedding function (will use local cache only)
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
            self.logger.info(f"Initialized embedding function: {self.embedding_model}")
        except Exception as e:
            self.logger.error(f"Failed to initialize embedding function: {e}")
            self.logger.error(
                "If running offline, please run 'python download_embedding_model.py' "
                "with internet connection first to download the model."
            )
            raise
    
    def _initialize_collections(self) -> None:
        """Initialize or get existing collections for all classes"""
        try:
            # Initialize embedding function first
            self._initialize_embedding_function()
            
            # Initialize each class collection
            for collection_name, description in self.collections_config.items():
                try:
                    # Try to get existing collection
                    collection = self.client.get_collection(
                        name=collection_name,
                        embedding_function=self.embedding_function
                    )
                    self.logger.info(f"Loaded existing collection: {collection_name}")
                    
                except ValueError:
                    # Collection doesn't exist, create it
                    collection = self.client.create_collection(
                        name=collection_name,
                        embedding_function=self.embedding_function,
                        metadata={"description": description}
                    )
                    self.logger.info(f"Created new collection: {collection_name}")
                
                self.collections[collection_name] = collection
            
            self.logger.info(f"Initialized {len(self.collections)} collections successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize collections: {e}")
            raise
    
    def add_question(self, class_num: int, question: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a question with embedding to the specified class collection
        
        Args:
            class_num: Class number (1-12)
            question: Question text to add
            metadata: Optional metadata dictionary
            
        Returns:
            Document ID of the added question
            
        Raises:
            ValueError: If class_num is invalid
        """
        collection_name = self._validate_class_num(class_num)
        
        try:
            collection = self.collections[collection_name]
            
            # Generate unique ID
            doc_id = str(uuid.uuid4())
            
            # Prepare metadata
            doc_metadata = {
                "class_num": class_num,
                "collection": collection_name,
                "timestamp": str(os.path.getctime(__file__)),
                "type": "question"
            }
            
            if metadata:
                doc_metadata.update(metadata)
            
            # Add to collection
            collection.add(
                ids=[doc_id],
                documents=[question],
                metadatas=[doc_metadata]
            )
            
            self.logger.debug(f"Added question to {collection_name}: {question[:50]}...")
            return doc_id
            
        except Exception as e:
            self.logger.error(f"Failed to add question to {collection_name}: {e}")
            raise
    
    def retrieve_similar(self, class_num: int, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Retrieve top-k similar documents using cosine similarity (OPTIMIZED)
        
        Args:
            class_num: Class number (1-12)
            query: Query text for similarity search
            top_k: Number of similar documents to retrieve
            
        Returns:
            ChromaDB query result format with documents, metadatas, distances
            
        Raises:
            ValueError: If class_num is invalid
        """
        collection_name = self._validate_class_num(class_num)
        
        try:
            collection = self.collections[collection_name]
            
            # OPTIMIZATION: Reduced multiplier for faster queries
            # Query the collection with filter to exclude inserted questions
            max_results = min(top_k * 2, collection.count(), 20)  # Cap at 20 for speed
            
            results = collection.query(
                query_texts=[query],
                n_results=max_results,
                include=['documents', 'metadatas', 'distances'],
                where={"type": {"$ne": "question"}}  # Exclude question-type documents
            )
            
            # If we didn't get enough results with filtering, try without filter
            if not results.get('documents') or len(results['documents'][0]) < top_k:
                self.logger.debug("Not enough results with filter, trying without filter")
                results = collection.query(
                    query_texts=[query],
                    n_results=min(top_k, collection.count()),
                    include=['documents', 'metadatas', 'distances']
                )
                
                # Filter out question-type documents manually
                if results.get('documents') and results['documents'][0]:
                    filtered_docs = []
                    filtered_metas = []
                    filtered_dists = []
                    
                    for doc, meta, dist in zip(
                        results['documents'][0],
                        results['metadatas'][0], 
                        results['distances'][0]
                    ):
                        # Skip question-type documents
                        if meta.get('type') != 'question':
                            filtered_docs.append(doc)
                            filtered_metas.append(meta)
                            filtered_dists.append(dist)
                        
                        # Stop when we have enough
                        if len(filtered_docs) >= top_k:
                            break
                    
                    # Update results with filtered data
                    results['documents'] = [filtered_docs]
                    results['metadatas'] = [filtered_metas]
                    results['distances'] = [filtered_dists]
            
            self.logger.debug(f"Retrieved {len(results.get('documents', [[]])[0])} similar documents from {collection_name}")
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve similar documents from {collection_name}: {e}")
            raise
    
    def get_collection_stats(self, class_num: int) -> Dict[str, Any]:
        """Return count and metadata for a collection
        
        Args:
            class_num: Class number (1-12)
            
        Returns:
            Dictionary with collection statistics
            
        Raises:
            ValueError: If class_num is invalid
        """
        collection_name = self._validate_class_num(class_num)
        
        try:
            collection = self.collections[collection_name]
            
            # Get basic stats
            count = collection.count()
            metadata = collection.metadata or {}
            
            # Get sample of documents for additional stats
            sample_size = min(10, count)
            sample_results = None
            
            if count > 0:
                try:
                    sample_results = collection.get(
                        limit=sample_size,
                        include=['documents', 'metadatas']
                    )
                except Exception as e:
                    self.logger.warning(f"Could not get sample documents: {e}")
            
            stats = {
                'collection_name': collection_name,
                'class_num': class_num,
                'document_count': count,
                'collection_metadata': metadata,
                'description': self.collections_config.get(collection_name, ''),
                'sample_size': sample_size
            }
            
            # Add sample document metadata analysis
            if sample_results and sample_results['metadatas']:
                metadata_keys = set()
                for doc_meta in sample_results['metadatas']:
                    if doc_meta:
                        metadata_keys.update(doc_meta.keys())
                
                stats['available_metadata_fields'] = list(metadata_keys)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get stats for {collection_name}: {e}")
            raise
    
    def batch_insert(self, class_num: int, questions_list: List[Dict[str, Any]]) -> List[str]:
        """Efficiently insert multiple questions
        
        Args:
            class_num: Class number (1-12)
            questions_list: List of dictionaries with 'question' and optional 'metadata' keys
            
        Returns:
            List of document IDs for inserted questions
            
        Raises:
            ValueError: If class_num is invalid or questions_list format is wrong
        """
        collection_name = self._validate_class_num(class_num)
        
        if not questions_list:
            self.logger.warning("Empty questions list provided for batch insert")
            return []
        
        try:
            collection = self.collections[collection_name]
            
            # Prepare batch data
            doc_ids = []
            documents = []
            metadatas = []
            
            for i, question_data in enumerate(questions_list):
                # Validate question data format
                if not isinstance(question_data, dict) or 'question' not in question_data:
                    raise ValueError(f"Invalid question data at index {i}. Must have 'question' key.")
                
                question_text = question_data['question']
                if not isinstance(question_text, str) or not question_text.strip():
                    raise ValueError(f"Invalid question text at index {i}. Must be non-empty string.")
                
                # Generate unique ID
                doc_id = str(uuid.uuid4())
                doc_ids.append(doc_id)
                documents.append(question_text)
                
                # Prepare metadata
                doc_metadata = {
                    "class_num": class_num,
                    "collection": collection_name,
                    "timestamp": str(os.path.getctime(__file__)),
                    "type": "question",
                    "batch_index": i
                }
                
                # Add custom metadata if provided
                custom_metadata = question_data.get('metadata', {})
                if custom_metadata:
                    doc_metadata.update(custom_metadata)
                
                metadatas.append(doc_metadata)
            
            # Batch insert to ChromaDB
            collection.add(
                ids=doc_ids,
                documents=documents,
                metadatas=metadatas
            )
            
            self.logger.info(f"Batch inserted {len(doc_ids)} questions to {collection_name}")
            return doc_ids
            
        except Exception as e:
            self.logger.error(f"Failed to batch insert questions to {collection_name}: {e}")
            raise
    
    def get_all_collection_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all class collections
        
        Returns:
            Dictionary mapping collection names to their statistics
        """
        all_stats = {}
        
        for class_num in range(1, 13):
            try:
                stats = self.get_collection_stats(class_num)
                collection_name = f"class{class_num}"
                all_stats[collection_name] = stats
            except Exception as e:
                self.logger.error(f"Failed to get stats for class {class_num}: {e}")
                all_stats[f"class{class_num}"] = {"error": str(e)}
        
        return all_stats
    
    def list_collections(self) -> List[str]:
        """List all available collection names
        
        Returns:
            List of collection names
        """
        return list(self.collections.keys())
    
    def get_collection_count(self, collection_name: str) -> int:
        """Get document count for a specific collection
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Number of documents in the collection
        """
        try:
            if collection_name in self.collections:
                collection = self.collections[collection_name]
                return collection.count()
            else:
                self.logger.warning(f"Collection {collection_name} not found")
                return 0
        except Exception as e:
            self.logger.error(f"Failed to get count for collection {collection_name}: {e}")
            return 0
    
    def reset_collection(self, class_num: int) -> None:
        """Reset a specific class collection (remove all documents)
        
        Args:
            class_num: Class number (1-12)
            
        Raises:
            ValueError: If class_num is invalid
        """
        collection_name = self._validate_class_num(class_num)
        
        try:
            # Delete the collection
            self.client.delete_collection(collection_name)
            
            # Recreate the collection
            description = self.collections_config[collection_name]
            collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": description}
            )
            
            # Update collections dict
            self.collections[collection_name] = collection
            
            self.logger.info(f"Collection {collection_name} reset successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to reset collection {collection_name}: {e}")
            raise
    
    def close(self) -> None:
        """Close database connections and clean up resources"""
        try:
            if hasattr(self, 'collections'):
                self.collections.clear()
            
            if hasattr(self, 'client'):
                # ChromaDB client doesn't have explicit close method
                self.client = None
            
            self.logger.info("ChromaDB handler closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing ChromaDB handler: {e}")
    
    @contextmanager
    def batch_operation(self):
        """Context manager for batch operations with proper resource cleanup"""
        try:
            self.logger.debug("Starting batch operation")
            yield self
        except Exception as e:
            self.logger.error(f"Error in batch operation: {e}")
            raise
        finally:
            self.logger.debug("Completed batch operation")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.close()
        if exc_type is not None:
            self.logger.error(f"Exception in context manager: {exc_val}")
        return False  # Don't suppress exceptions