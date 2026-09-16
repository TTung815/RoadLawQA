# -*- coding: utf-8 -*-
"""
Application Settings & Configuration Module (Additive for V2 Foundation)
Does not require GEMINI_API_KEY at import time.
"""
import os
from pathlib import Path
from typing import ClassVar, Dict, Optional
from pydantic import BaseModel, Field
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AppSettings(BaseModel):
    """Liveness app configuration, independent of retrieval resources."""
    # App
    app_name: str = "VietLaw-Agent"
    app_version: str = "2.0.0"
    debug: bool = False

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000


class LLMSettings(AppSettings):
    """LLM configuration without validation of unrelated retrieval settings.

    Read the project .env without mutating the process environment. Explicit
    arguments override environment variables, which override .env values.
    """

    _env_fields: ClassVar[Dict[str, str]] = {
        "gemini_api_key": "GEMINI_API_KEY",
        "gemini_model_name": "GEMINI_MODEL_NAME",
    }
    gemini_api_key: Optional[str] = None
    gemini_model_name: str = "gemini-2.5-flash"

    def __init__(self, **values):
        file_values = dotenv_values(PROJECT_ROOT / ".env")
        defaults = {
            field: os.environ.get(env_key, file_values.get(env_key))
            for field, env_key in self._env_fields.items()
            if env_key in os.environ or file_values.get(env_key) is not None
        }
        super().__init__(**{**defaults, **values})


class Settings(LLMSettings):
    """Full resource settings validated only when explicitly instantiated."""

    _env_fields: ClassVar[Dict[str, str]] = {
        **LLMSettings._env_fields,
        "weaviate_host": "WEAVIATE_HOST",
        "weaviate_port": "WEAVIATE_PORT",
        "weaviate_grpc_port": "WEAVIATE_GRPC_PORT",
    }

    # Paths
    project_root: Path = PROJECT_ROOT
    bm25_index_path: Path = PROJECT_ROOT / "bm25_index.pkl"
    data_dir: Path = PROJECT_ROOT / "data"

    # Weaviate
    weaviate_host: str = "localhost"
    weaviate_port: int = Field(default=8080, ge=1, le=65535)
    weaviate_grpc_port: int = Field(default=50051, ge=1, le=65535)
    weaviate_collection: str = "LawChunks"

    # Retrieval Models
    embedding_model: str = "Alibaba-NLP/gte-multilingual-base"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Retrieval Tuning
    default_top_k: int = 5
    candidate_multiplier: int = 4


_global_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _global_settings
    if _global_settings is None:
        _global_settings = Settings()
    return _global_settings
