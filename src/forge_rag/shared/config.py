import base64
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    environment: Literal["development", "production"] = "development"
    database_url: str = Field(default="sqlite:///./data/rag.db", repr=False)
    delegation_keys: dict[str, SecretStr] = Field(default_factory=dict, repr=False)
    delegation_audience: str = "modular-forge-rag"
    embedding_provider: Literal["hash", "openai", "ollama"] = "hash"
    embedding_model: str = ""
    embedding_revision: str = Field(default="1", min_length=1, max_length=128)
    embedding_dimensions: int = Field(default=256, ge=16, le=4096)
    generation_provider: Literal["extractive", "openai", "ollama"] = "extractive"
    generation_model: str = ""
    openai_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    ollama_url: str = "http://127.0.0.1:11434"
    provider_timeout_seconds: float = Field(default=30, ge=1, le=60)
    module_ingestion_enabled: bool = True
    module_pdf_enabled: bool = False
    module_reranking_enabled: bool = False
    module_evaluation_enabled: bool = True
    module_telemetry_enabled: bool = True
    module_api_docs_enabled: bool = True
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    chunk_chars: int = Field(default=1000, ge=200, le=1500)
    chunk_overlap: int = Field(default=120, ge=0, le=300)
    max_document_bytes: int = Field(default=1_000_000, ge=100, le=5_000_000)
    max_chunks: int = Field(default=256, ge=1, le=1000)
    max_context_chars: int = Field(default=8000, ge=1500, le=20000)
    min_similarity: float = Field(default=0.3, ge=0, le=1)
    candidate_limit: int = Field(default=50, ge=10, le=200)
    sqlite_max_chunks: int = Field(default=10000, ge=10, le=100000)
    job_lease_seconds: int = Field(default=300, ge=30, le=3600)
    job_max_attempts: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_settings(self):
        if self.chunk_overlap >= self.chunk_chars:
            raise ValueError("chunk_overlap must be smaller than chunk_chars")
        if not self.delegation_keys:
            raise ValueError("DELEGATION_KEYS is required; run forge-rag init-env")
        decoded = []
        for issuer, secret in self.delegation_keys.items():
            if not issuer or ":" in issuer or len(issuer) > 64:
                raise ValueError("Delegation issuer must be 1-64 characters without ':'")
            try:
                key = base64.b64decode(secret.get_secret_value(), validate=True)
            except ValueError as exc:
                raise ValueError("Delegation keys must be Base64") from exc
            if len(key) != 32 or len(set(key)) < 16:
                raise ValueError("Delegation keys must contain 32 random bytes")
            decoded.append(key)
        if len(set(decoded)) != len(decoded):
            raise ValueError("Use a distinct delegation key for each backend")
        if self.embedding_provider != "hash" and not self.embedding_model:
            raise ValueError("EMBEDDING_MODEL is required for a live provider")
        if self.generation_provider != "extractive" and not self.generation_model:
            raise ValueError("GENERATION_MODEL is required for a live provider")
        if (
            "openai" in (self.embedding_provider, self.generation_provider)
            and not self.openai_api_key.get_secret_value()
        ):
            raise ValueError("OPENAI_API_KEY is required")
        parsed = urlparse(self.ollama_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OLLAMA_URL must be a server-controlled HTTP(S) origin")
        if parsed.path not in {"", "/"}:
            raise ValueError("OLLAMA_URL must not contain a path")
        if self.environment == "production":
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires PostgreSQL/pgvector")
            if self.module_api_docs_enabled or "*" in self.allowed_hosts:
                raise ValueError("Disable API docs and use explicit hosts in production")
            if (
                "ollama" in (self.embedding_provider, self.generation_provider)
                and parsed.scheme != "https"
            ):
                raise ValueError("Production Ollama transport requires HTTPS")
        return self

    def key(self, issuer: str) -> bytes:
        return base64.b64decode(self.delegation_keys[issuer].get_secret_value(), validate=True)
