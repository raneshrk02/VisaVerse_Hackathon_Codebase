"""
Brief: Type-safe configuration loader that resolves portable paths for USB deployments.

Loads YAML, applies defaults, and dynamically adjusts paths to the USB root when available.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum


class LogLevel(Enum):
    """Logging levels enum"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class AppConfig:
    """Application configuration"""
    name: str = "SAGE RAG System"
    version: str = "1.0.0"
    description: str = "Educational Content Q&A System"


@dataclass
class PathsConfig:
    """File paths configuration"""
    models_dir: str = "models"
    chromadb_dir: str = "../data/ncert_chromadb"
    embeddings_dir: str = "embeddings"
    logs_dir: str = "logs"
    processed_data_dir: str = "processed_data"


@dataclass
class CollectionConfig:
    """ChromaDB collection configuration"""
    name: str
    description: str = ""


@dataclass
class ChromaDBConfig:
    """ChromaDB configuration"""
    persist_directory: str = "../data/ncert_chromadb"
    embedding_function: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    collections: List[CollectionConfig] = field(default_factory=lambda: [
        CollectionConfig(name=f"class{i}", description=f"Class {i} NCERT content")
        for i in range(1, 13)
    ])


@dataclass
class LLMConfig:
    """LLM configuration"""
    model_name: str = "phi-2"
    model_path: str = "./models/phi2/phi-2.Q4_K_M.gguf"
    context_length: int = 2048
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 40
    repeat_penalty: float = 1.1
    n_ctx: int = 2048
    n_batch: int = 8
    n_threads: int = -1
    verbose: bool = False


@dataclass
class RetrievalConfig:
    """RAG retrieval configuration"""
    top_k: int = 5
    similarity_threshold: float = 0.7
    rerank: bool = True


@dataclass
class GenerationConfig:
    """RAG generation configuration"""
    max_context_length: int = 1500
    system_prompt: str = field(default_factory=lambda: """You are SAGE, an educational AI assistant specialized in NCERT curriculum content. Your role is to provide accurate, age-appropriate educational answers based strictly on the provided context from NCERT textbooks.

GUIDELINES:
1. Only answer based on the provided context from NCERT materials
2. If the context doesn't contain sufficient information, clearly state this
3. Provide explanations appropriate for the student's class level
4. Use simple, clear language that students can understand
5. When explaining concepts, provide examples where helpful
6. Do not provide information outside the NCERT curriculum scope
7. Encourage further learning and curiosity
8. If asked about inappropriate content, politely redirect to educational topics

Remember: Your purpose is to support student learning within the NCERT educational framework.""")
    prompt_template: str = field(default_factory=lambda: """{system_prompt}

Context from NCERT materials: {context}

Student Question: {question}

Educational Answer:""")


@dataclass
class RAGConfig:
    """RAG pipeline configuration"""
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)


@dataclass
class GuiColors:
    """GUI color configuration"""
    primary: str = "#2E86AB"
    secondary: str = "#A23B72"
    background: str = "#F18F01"
    text: str = "#C73E1D"


@dataclass
class GuiConfig:
    """GUI configuration"""
    title: str = "SAGE RAG - Educational Q&A System"
    window_size: str = "800x600"
    theme: str = "default"
    font_family: str = "Arial"
    font_size: int = 10
    colors: GuiColors = field(default_factory=GuiColors)


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_file_size: str = "10MB"
    backup_count: int = 5


@dataclass
class PerformanceConfig:
    """Performance configuration"""
    cache_embeddings: bool = True
    cache_dir: str = "embeddings"
    max_cache_size: str = "1GB"


@dataclass
class DocumentProcessingConfig:
    """Document processing configuration"""
    supported_formats: List[str] = field(default_factory=lambda: ["txt", "pdf", "md"])
    text_splitter: str = "recursive"
    metadata_extraction: bool = True


@dataclass
class ModelDownloadConfig:
    """Model download configuration"""
    phi2_url: str = "https://huggingface.co/microsoft/phi-2-gguf"
    embedding_model_url: str = "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2"
    auto_download: bool = False


@dataclass
class Config:
    """Main configuration class"""
    app: AppConfig = field(default_factory=AppConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    chromadb: ChromaDBConfig = field(default_factory=ChromaDBConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    document_processing: DocumentProcessingConfig = field(default_factory=DocumentProcessingConfig)
    model_download: ModelDownloadConfig = field(default_factory=ModelDownloadConfig)


class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors"""
    pass


class ConfigLoader:
    """Type-safe configuration loader with validation"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize config loader
        
        Args:
            config_path: Path to configuration file (default: config.yaml)
        """
        self.config_path = config_path or "config.yaml"
        self.logger = logging.getLogger(__name__)
        self._usb_root = self._detect_usb_root()
    def _detect_usb_root(self) -> Path:
        """Detect usb-deploy root or fallback to project root."""
        env_root = os.getenv("USB_ROOT")
        if env_root:
            try:
                p = Path(env_root).expanduser().resolve()
                if p.exists():
                    return p
            except Exception:
                pass
        here = Path(__file__).resolve()
        for parent in here.parents:
            if (parent.name == "usb-deploy") or ((parent / "setup").exists() and (parent / "scripts").exists()):
                return parent
        # src/config_loader.py → src → rag_api → backend → usb-deploy
        try:
            return here.parents[4]
        except Exception:
            return Path(__file__).resolve().parents[2]
        
    def load_config(self) -> Config:
        """Load configuration from YAML file with validation
        
        Returns:
            Config object with validated settings
            
        Raises:
            ConfigValidationError: If configuration is invalid
        """
        try:
            # Load YAML file if it exists, otherwise use defaults
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    yaml_data = yaml.safe_load(file) or {}
                self.logger.info(f"Loaded configuration from {self.config_path}")
            else:
                yaml_data = {}
                self.logger.warning(f"Configuration file {self.config_path} not found, using defaults")
            
            # Create configuration object with defaults
            config = self._create_config_from_dict(yaml_data)
            
            # Validate configuration
            self._validate_config(config)
            
            return config
            
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Error loading configuration: {e}")
    
    def _create_config_from_dict(self, data: Dict[str, Any]) -> Config:
        """Create Config object from dictionary data with defaults"""
        
        # Helper function to safely get nested values
        def get_nested(d: Dict, keys: List[str], default=None):
            for key in keys:
                if isinstance(d, dict) and key in d:
                    d = d[key]
                else:
                    return default
            return d
        
        # Create configuration sections
        app_data = data.get('app', {})
        app_config = AppConfig(
            name=app_data.get('name', AppConfig().name),
            version=app_data.get('version', AppConfig().version),
            description=app_data.get('description', AppConfig().description)
        )
        
        paths_data = data.get('paths', {})
        # Resolve portable paths relative to usb root when provided
        default_paths = PathsConfig()
        chroma_dir = paths_data.get('chromadb_dir', default_paths.chromadb_dir)
        if chroma_dir.startswith("../data/") or chroma_dir.startswith("./data/"):
            chroma_dir = str((self._usb_root / chroma_dir.replace("./", "").replace("../", "")).resolve())
        paths_config = PathsConfig(
            models_dir=paths_data.get('models_dir', default_paths.models_dir),
            chromadb_dir=chroma_dir,
            embeddings_dir=paths_data.get('embeddings_dir', default_paths.embeddings_dir),
            logs_dir=paths_data.get('logs_dir', default_paths.logs_dir),
            processed_data_dir=paths_data.get('processed_data_dir', default_paths.processed_data_dir)
        )
        
        chromadb_data = data.get('chromadb', {})
        collections_data = chromadb_data.get('collections', [])
        collections = []
        
        if collections_data:
            for col_data in collections_data:
                if isinstance(col_data, dict):
                    collections.append(CollectionConfig(
                        name=col_data.get('name', ''),
                        description=col_data.get('description', '')
                    ))
        else:
            # Use default collections
            collections = ChromaDBConfig().collections
        
        chroma_persist = chromadb_data.get('persist_directory', ChromaDBConfig().persist_directory)
        if chroma_persist.startswith("../data/") or chroma_persist.startswith("./data/"):
            chroma_persist = str((self._usb_root / chroma_persist.replace("./", "").replace("../", "")).resolve())
        chromadb_config = ChromaDBConfig(
            persist_directory=chroma_persist,
            embedding_function=chromadb_data.get('embedding_function', ChromaDBConfig().embedding_function),
            chunk_size=chromadb_data.get('chunk_size', ChromaDBConfig().chunk_size),
            chunk_overlap=chromadb_data.get('chunk_overlap', ChromaDBConfig().chunk_overlap),
            collections=collections
        )
        
        llm_data = data.get('llm', {})
        llm_config = LLMConfig(
            model_name=llm_data.get('model_name', LLMConfig().model_name),
            model_path=llm_data.get('model_path', LLMConfig().model_path),
            context_length=llm_data.get('context_length', LLMConfig().context_length),
            max_tokens=llm_data.get('max_tokens', LLMConfig().max_tokens),
            temperature=llm_data.get('temperature', LLMConfig().temperature),
            top_p=llm_data.get('top_p', LLMConfig().top_p),
            top_k=llm_data.get('top_k', LLMConfig().top_k),
            repeat_penalty=llm_data.get('repeat_penalty', LLMConfig().repeat_penalty),
            n_ctx=llm_data.get('n_ctx', LLMConfig().n_ctx),
            n_batch=llm_data.get('n_batch', LLMConfig().n_batch),
            n_threads=llm_data.get('n_threads', LLMConfig().n_threads),
            verbose=llm_data.get('verbose', LLMConfig().verbose)
        )
        
        rag_data = data.get('rag', {})
        retrieval_data = rag_data.get('retrieval', {})
        generation_data = rag_data.get('generation', {})
        
        retrieval_config = RetrievalConfig(
            top_k=retrieval_data.get('top_k', RetrievalConfig().top_k),
            similarity_threshold=retrieval_data.get('similarity_threshold', RetrievalConfig().similarity_threshold),
            rerank=retrieval_data.get('rerank', RetrievalConfig().rerank)
        )
        
        generation_config = GenerationConfig(
            max_context_length=generation_data.get('max_context_length', GenerationConfig().max_context_length),
            system_prompt=generation_data.get('system_prompt', GenerationConfig().system_prompt),
            prompt_template=generation_data.get('prompt_template', GenerationConfig().prompt_template)
        )
        
        rag_config = RAGConfig(
            retrieval=retrieval_config,
            generation=generation_config
        )
        
        gui_data = data.get('gui', {})
        colors_data = gui_data.get('colors', {})
        
        gui_colors = GuiColors(
            primary=colors_data.get('primary', GuiColors().primary),
            secondary=colors_data.get('secondary', GuiColors().secondary),
            background=colors_data.get('background', GuiColors().background),
            text=colors_data.get('text', GuiColors().text)
        )
        
        gui_config = GuiConfig(
            title=gui_data.get('title', GuiConfig().title),
            window_size=gui_data.get('window_size', GuiConfig().window_size),
            theme=gui_data.get('theme', GuiConfig().theme),
            font_family=gui_data.get('font_family', GuiConfig().font_family),
            font_size=gui_data.get('font_size', GuiConfig().font_size),
            colors=gui_colors
        )
        
        logging_data = data.get('logging', {})
        logging_config = LoggingConfig(
            level=logging_data.get('level', LoggingConfig().level),
            format=logging_data.get('format', LoggingConfig().format),
            max_file_size=logging_data.get('max_file_size', LoggingConfig().max_file_size),
            backup_count=logging_data.get('backup_count', LoggingConfig().backup_count)
        )
        
        performance_data = data.get('performance', {})
        performance_config = PerformanceConfig(
            cache_embeddings=performance_data.get('cache_embeddings', PerformanceConfig().cache_embeddings),
            cache_dir=performance_data.get('cache_dir', PerformanceConfig().cache_dir),
            max_cache_size=performance_data.get('max_cache_size', PerformanceConfig().max_cache_size)
        )
        
        doc_proc_data = data.get('document_processing', {})
        doc_proc_config = DocumentProcessingConfig(
            supported_formats=doc_proc_data.get('supported_formats', DocumentProcessingConfig().supported_formats),
            text_splitter=doc_proc_data.get('text_splitter', DocumentProcessingConfig().text_splitter),
            metadata_extraction=doc_proc_data.get('metadata_extraction', DocumentProcessingConfig().metadata_extraction)
        )
        
        model_dl_data = data.get('model_download', {})
        model_dl_config = ModelDownloadConfig(
            phi2_url=model_dl_data.get('phi2_url', ModelDownloadConfig().phi2_url),
            embedding_model_url=model_dl_data.get('embedding_model_url', ModelDownloadConfig().embedding_model_url),
            auto_download=model_dl_data.get('auto_download', ModelDownloadConfig().auto_download)
        )
        
        return Config(
            app=app_config,
            paths=paths_config,
            chromadb=chromadb_config,
            llm=llm_config,
            rag=rag_config,
            gui=gui_config,
            logging=logging_config,
            performance=performance_config,
            document_processing=doc_proc_config,
            model_download=model_dl_config
        )
    
    def _validate_config(self, config: Config) -> None:
        """Validate configuration settings
        
        Args:
            config: Configuration object to validate
            
        Raises:
            ConfigValidationError: If configuration is invalid
        """
        errors = []
        
        # Validate paths exist or can be created
        paths_to_check = [
            (config.paths.models_dir, "models directory"),
            (config.paths.logs_dir, "logs directory"),
            (config.paths.embeddings_dir, "embeddings directory"),
            (config.chromadb.persist_directory, "ChromaDB directory")
        ]
        
        for path, description in paths_to_check:
            if not self._validate_path(path, create_if_missing=True):
                errors.append(f"Cannot access or create {description}: {path}")
        
        # Validate model file exists if not auto-download
        if not config.model_download.auto_download:
            model_path = Path(config.llm.model_path)
            if not model_path.exists():
                errors.append(f"Model file not found: {config.llm.model_path}. "
                            f"Please download the model or enable auto_download.")
        
        # Validate numeric ranges
        if not (0.0 <= config.llm.temperature <= 2.0):
            errors.append(f"Invalid temperature: {config.llm.temperature}. Must be between 0.0 and 2.0")
        
        if not (0.0 <= config.llm.top_p <= 1.0):
            errors.append(f"Invalid top_p: {config.llm.top_p}. Must be between 0.0 and 1.0")
        
        if not (0.0 <= config.rag.retrieval.similarity_threshold <= 1.0):
            errors.append(f"Invalid similarity_threshold: {config.rag.retrieval.similarity_threshold}. "
                         f"Must be between 0.0 and 1.0")
        
        if config.rag.retrieval.top_k <= 0:
            errors.append(f"Invalid top_k: {config.rag.retrieval.top_k}. Must be positive")
        
        if config.llm.max_tokens <= 0:
            errors.append(f"Invalid max_tokens: {config.llm.max_tokens}. Must be positive")
        
        if config.llm.context_length <= 0:
            errors.append(f"Invalid context_length: {config.llm.context_length}. Must be positive")
        
        # Validate collections
        if not config.chromadb.collections:
            errors.append("No collections defined in ChromaDB configuration")
        else:
            collection_names = [col.name for col in config.chromadb.collections]
            if len(collection_names) != len(set(collection_names)):
                errors.append("Duplicate collection names found")
        
        # Validate logging level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if config.logging.level not in valid_levels:
            errors.append(f"Invalid logging level: {config.logging.level}. "
                         f"Must be one of: {valid_levels}")
        
        if errors:
            raise ConfigValidationError(f"Configuration validation failed:\n" + "\n".join(errors))
        
        self.logger.info("Configuration validation passed")
    
    def _validate_path(self, path: str, create_if_missing: bool = False) -> bool:
        """Validate a path exists or can be created
        
        Args:
            path: Path to validate
            create_if_missing: Whether to create the path if it doesn't exist
            
        Returns:
            True if path is valid, False otherwise
        """
        try:
            path_obj = Path(path)
            
            if path_obj.exists():
                return True
            
            if create_if_missing:
                path_obj.mkdir(parents=True, exist_ok=True)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error validating path {path}: {e}")
            return False
    
    def save_config(self, config: Config, output_path: Optional[str] = None) -> None:
        """Save configuration to YAML file
        
        Args:
            config: Configuration object to save
            output_path: Output file path (default: same as config_path)
        """
        output_path = output_path or self.config_path
        
        # Convert config to dictionary
        config_dict = self._config_to_dict(config)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as file:
                yaml.dump(config_dict, file, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            
            self.logger.info(f"Configuration saved to {output_path}")
            
        except Exception as e:
            raise ConfigValidationError(f"Error saving configuration: {e}")
    
    def _config_to_dict(self, config: Config) -> Dict[str, Any]:
        """Convert Config object to dictionary for YAML serialization"""
        # This would be a comprehensive conversion - simplified for brevity
        return {
            'app': {
                'name': config.app.name,
                'version': config.app.version,
                'description': config.app.description
            },
            'paths': {
                'models_dir': config.paths.models_dir,
                'chromadb_dir': config.paths.chromadb_dir,
                'embeddings_dir': config.paths.embeddings_dir,
                'logs_dir': config.paths.logs_dir,
                'processed_data_dir': config.paths.processed_data_dir
            },
            # ... (other sections would be similar)
        }


def load_config(config_path: Optional[str] = None) -> Config:
    """Convenience function to load configuration
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Loaded and validated configuration
    """
    loader = ConfigLoader(config_path)
    return loader.load_config()