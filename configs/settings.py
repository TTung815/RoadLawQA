# -*- coding: utf-8 -*-
"""
Application Settings & Configuration Module (Additive for V2 Foundation)
Does not require GEMINI_API_KEY at import time.
"""
import os
from pathlib import Path
from typing import ClassVar, Dict, Literal, Optional
from pydantic import BaseModel, Field, model_validator
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
    Selects Gemini/OpenAI without initializing clients. Legacy GEMINI_* settings
    remain valid; LLM_MODEL_NAME takes precedence for the selected provider.
    """

    _env_fields: ClassVar[Dict[str, str]] = {
        "gemini_api_key": "GEMINI_API_KEY",
        "gemini_api_keys": "GEMINI_API_KEYS",
        "gemini_model_name": "GEMINI_MODEL_NAME",
        "llm_provider": "LLM_PROVIDER",
        "llm_model_name": "LLM_MODEL_NAME",
        "openai_api_key": "OPENAI_API_KEY",
        "openai_reasoning_effort": "OPENAI_REASONING_EFFORT",
        "openai_max_output_tokens": "OPENAI_MAX_OUTPUT_TOKENS",
        "llm_request_timeout_seconds": "LLM_REQUEST_TIMEOUT_SECONDS",
        "llm_max_transient_retries": "LLM_MAX_TRANSIENT_RETRIES",
        "structural_expansion_enabled": "STRUCTURAL_EXPANSION_ENABLED",
        "warmup_on_startup": "WARMUP_ON_STARTUP",
        "router_reasoning_effort": "ROUTER_REASONING_EFFORT",
    }
    gemini_api_key: Optional[str] = None
    gemini_api_keys: list[str] = Field(default_factory=list)
    gemini_model_name: str = "gemini-2.5-flash"
    llm_provider: Literal["gemini", "openai"] = "gemini"
    llm_model_name: Optional[str] = Field(default=None, min_length=1)
    openai_api_key: Optional[str] = None
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "medium"
    openai_max_output_tokens: int = Field(default=16384, ge=1)
    llm_request_timeout_seconds: float = Field(default=90.0, gt=0, allow_inf_nan=False)
    llm_max_transient_retries: int = Field(default=2, ge=0, le=5)
    # Compatibility setting for old experiments; serving always searches once.
    structural_expansion_enabled: bool = True
    # Load retrieval models/index in the background when the API starts.
    warmup_on_startup: bool = True
    # OpenAI only: the router classifies intent and rewrites the query, so it
    # can use less reasoning than generation/verification. None reuses
    # openai_reasoning_effort.
    router_reasoning_effort: Optional[Literal["none", "low", "medium", "high", "xhigh", "max"]] = "low"

    @property
    def model_name(self) -> str:
        if self.llm_model_name is not None:
            return self.llm_model_name
        return self.gemini_model_name if self.llm_provider == "gemini" else "gpt-6-luna"

    def __init__(self, **values):
        file_values = dotenv_values(PROJECT_ROOT / ".env")
        defaults = {
            field: os.environ.get(env_key, file_values.get(env_key))
            for field, env_key in self._env_fields.items()
            if env_key in os.environ or file_values.get(env_key) is not None
        }

        # Resolve list of keys and single key
        if "gemini_api_key" in values and values["gemini_api_key"] is None and "gemini_api_keys" not in values:
            single_key = None
            keys_list = []
        else:
            raw_keys = values.get("gemini_api_keys", defaults.get("gemini_api_keys"))
            raw_single = values.get("gemini_api_key", defaults.get("gemini_api_key"))

            keys_list = []
            if isinstance(raw_keys, list):
                keys_list = [k.strip() for k in raw_keys if isinstance(k, str) and k.strip()]
            elif isinstance(raw_keys, str) and raw_keys.strip():
                keys_list = [k.strip() for k in raw_keys.split(",") if k.strip()]

            # GEMINI_API_KEYS takes precedence over GEMINI_API_KEY
            if keys_list:
                single_key = keys_list[0]
            elif isinstance(raw_single, str) and raw_single.strip():
                keys_list = [k.strip() for k in raw_single.split(",") if k.strip()]
                single_key = keys_list[0] if keys_list else None
            else:
                single_key = None

        super().__init__(**{
            **defaults,
            **values,
            "gemini_api_key": single_key,
            "gemini_api_keys": keys_list,
        })


class Settings(LLMSettings):
    """Full resource settings validated only when explicitly instantiated."""

    _env_fields: ClassVar[Dict[str, str]] = {
        **LLMSettings._env_fields,
        "weaviate_host": "WEAVIATE_HOST",
        "weaviate_port": "WEAVIATE_PORT",
        "weaviate_grpc_port": "WEAVIATE_GRPC_PORT",
        "reranker_revision": "RERANKER_REVISION",
        "retrieval_backend": "RETRIEVAL_BACKEND",
        "hybrid_alpha": "HYBRID_ALPHA",
        "hybrid_candidate_limit": "HYBRID_CANDIDATE_LIMIT",
        "compound_candidate_limit": "COMPOUND_CANDIDATE_LIMIT",
        "reranker_batch_size": "RERANKER_BATCH_SIZE",
        "embedding_device": "EMBEDDING_DEVICE",
        "reranker_device": "RERANKER_DEVICE",
    }

    # Paths
    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"

    # Weaviate
    weaviate_host: str = "localhost"
    weaviate_port: int = Field(default=8080, ge=1, le=65535)
    weaviate_grpc_port: int = Field(default=50051, ge=1, le=65535)
    weaviate_collection: str = "LawStructured20260922V2"
    retrieval_backend: Literal["structured"] = "structured"
    hybrid_alpha: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    hybrid_candidate_limit: int = Field(default=20, ge=20, le=40)
    compound_candidate_limit: int = Field(default=32, ge=20, le=40)
    reranker_batch_size: int = Field(default=4, ge=1, le=32)
    # Short, one-query embeddings are faster on CPU in the local MPS demo.
    embedding_device: Literal["auto", "cpu", "mps", "cuda"] = "cpu"
    reranker_device: Literal["auto", "cpu", "mps", "cuda"] = "auto"

    # Retrieval Models
    embedding_model: str = "Alibaba-NLP/gte-multilingual-base"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_revision: str = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"

    # Retrieval Tuning
    default_top_k: int = 10
    candidate_multiplier: int = 4

    @model_validator(mode="after")
    def candidate_budgets(self):
        if self.compound_candidate_limit < self.hybrid_candidate_limit:
            raise ValueError("compound_candidate_limit must be >= hybrid_candidate_limit")
        return self


_global_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _global_settings
    if _global_settings is None:
        _global_settings = Settings()
    return _global_settings
