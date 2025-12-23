"""
Brief: Centralized configuration with portable USB path detection and env overrides.

Detects the USB root dynamically and resolves default paths to be portable.
All paths can still be overridden via environment variables.
"""

import os
from typing import List, Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache
def _detect_usb_root() -> Path:
    """Detect USB deployment root directory.

    Order:
    - USB_ROOT env (absolute or relative)
    - Walk up from this file to find a directory named 'usb-deploy'
    - If current layout is usb-deploy/backend/rag_api → return parent of 'backend'
    - Fallback to project root two levels up from this file
    - Final fallback: current working directory
    """
    env_root = os.getenv("USB_ROOT")
    if env_root:
        try:
            root = Path(env_root).expanduser().resolve()
            if root.exists():
                return root
        except Exception:
            pass

    here = Path(__file__).resolve()
    # Try to find 'usb-deploy' up the tree
    for parent in here.parents:
        if (parent.name == "usb-deploy") or ((parent / "scripts").exists() and (parent / "setup").exists()):
            return parent

    # If in usb-deploy/backend/rag_api, usb root is three parents up from file
    # app/core/config.py → app/core → app → rag_api → backend → usb-deploy
    try:
        usb_root = here.parents[4]
        if (usb_root / "backend").exists() and (usb_root / "frontend").exists():
            return usb_root
    except Exception:
        pass

    # Fallback: project root (rag_api parent) or CWD
    project_root = here.parents[3] if len(here.parents) >= 4 else Path.cwd()
    return project_root


@lru_cache(maxsize=1)
def USB_ROOT() -> Path:
    return _detect_usb_root()


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file
    """
    
    # Application settings
    app_name: str = Field(default="SAGE RAG API", env="APP_NAME")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8001, env="PORT")
    
    # Security settings
    secret_key: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="ALLOWED_ORIGINS"
    )
    
    # gRPC settings
    grpc_host: str = Field(default="0.0.0.0", env="GRPC_HOST")
    grpc_port: int = Field(default=50051, env="GRPC_PORT")
    
    # ChromaDB settings
    chromadb_path: str = Field(default="", env="CHROMADB_PATH")
    
    # LLM settings
    model_path: str = Field(default="", env="MODEL_PATH")
    
    # RAG configuration
    max_retrieval_results: int = Field(default=5, env="MAX_RETRIEVAL_RESULTS")
    similarity_threshold: float = Field(default=0.7, env="SIMILARITY_THRESHOLD")
    max_context_length: int = Field(default=1500, env="MAX_CONTEXT_LENGTH")
    
    # Logging
    log_dir: str = Field(default="logs", env="LOG_DIR")
    log_file: str = Field(default="rag_api.log", env="LOG_FILE")
    
    # Performance
    enable_caching: bool = Field(default=True, env="ENABLE_CACHING")
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")  # seconds
    max_cache_size: int = Field(default=1000, env="MAX_CACHE_SIZE")
    
    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds
    
    # Monitoring
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=8002, env="METRICS_PORT")
    
    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        """Parse comma-separated origins"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @field_validator("chromadb_path", "model_path")
    @classmethod
    def validate_paths(cls, v):
        """Validate that paths exist or can be created"""
        # If empty, fill defaults based on detected USB root
        if not v:
            # Determine which field is being validated by inspecting call stack would be brittle;
            # instead infer by common substrings.
            # chromadb default: <USB_ROOT>/data/ncert_chromadb
            # model default:    <rag_api>/models/phi2/phi-2.Q4_K_M.gguf
            v = "chromadb" if "chromadb" in cls.__name__.lower() else v

        path = Path(v)
        if not path.exists():
            # For ChromaDB path, try to create it
            if "chromadb" in str(path).lower():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass  # Will be handled during initialization
        return str(path.absolute())
    
    @property
    def chromadb_absolute_path(self) -> Path:
        """Get absolute path to ChromaDB directory"""
        # Env override takes precedence; else default under USB root
        if self.chromadb_path:
            return Path(self.chromadb_path).expanduser().resolve()
        return (USB_ROOT() / "data" / "ncert_chromadb").resolve()
    
    @property
    def model_absolute_path(self) -> Path:
        """Get absolute path to model file"""
        if self.model_path:
            return Path(self.model_path).expanduser().resolve()
        # Default to local models within rag_api
        app_dir = Path(__file__).resolve().parents[2]  # rag_api
        return (app_dir / "models" / "phi2" / "phi-2.Q4_K_M.gguf").resolve()
    
    @property
    def log_absolute_path(self) -> Path:
        """Get absolute path to log directory"""
        # Logs default to rag_api/logs to keep app self-contained
        app_dir = Path(__file__).resolve().parents[2]
        return (app_dir / self.log_dir).resolve()
    
    def create_directories(self):
        """Create necessary directories"""
        directories = [
            self.log_absolute_path,
            self.chromadb_absolute_path.parent if self.chromadb_absolute_path.is_file() else self.chromadb_absolute_path
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Ensure directories exist
settings.create_directories()