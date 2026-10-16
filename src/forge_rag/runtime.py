from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from forge_rag.chunking.character import CharacterChunker
from forge_rag.persistence.store import SQLRepository
from forge_rag.retrieval.service import QueryService
from forge_rag.shared.config import Settings
from forge_rag.shared.ports import Embedder, Extractor, Generator, Repository

if TYPE_CHECKING:
    from forge_rag.ingestion.service import IngestionService
    from forge_rag.ingestion.worker import Worker


@dataclass
class Runtime:
    settings: Settings
    repository: Repository
    query: QueryService
    ingestion: IngestionService | None = None
    worker: Worker | None = None
    closers: list[Callable] = field(default_factory=list)

    def close(self):
        for closer in reversed(self.closers):
            closer()
        self.repository.close()


def build_runtime(
    settings: Settings,
    *,
    repository: Repository | None = None,
    embedder: Embedder | None = None,
    generator: Generator | None = None,
):
    closers = []
    clients = {}

    def http(provider):
        if provider not in clients:
            from forge_rag.providers.http import ProviderHTTP

            client = ProviderHTTP(
                "https://api.openai.com/v1" if provider == "openai" else settings.ollama_url,
                settings.provider_timeout_seconds,
                key=settings.openai_api_key.get_secret_value() if provider == "openai" else "",
            )
            clients[provider] = client
            closers.append(client.close)
        return clients[provider]

    if embedder is None:
        if settings.embedding_provider == "hash":
            from forge_rag.providers.offline import HashEmbedder

            embedder = HashEmbedder(settings.embedding_dimensions)
        elif settings.embedding_provider == "openai":
            from forge_rag.providers.openai import OpenAIEmbedder

            embedder = OpenAIEmbedder(
                http("openai"), settings.embedding_model, settings.embedding_dimensions
            )
        else:
            from forge_rag.providers.ollama import OllamaEmbedder

            embedder = OllamaEmbedder(
                http("ollama"), settings.embedding_model, settings.embedding_dimensions
            )
    if generator is None:
        if settings.generation_provider == "extractive":
            from forge_rag.providers.offline import ExtractiveGenerator

            generator = ExtractiveGenerator()
        elif settings.generation_provider == "openai":
            from forge_rag.providers.openai import OpenAIGenerator

            generator = OpenAIGenerator(http("openai"), settings.generation_model)
        else:
            from forge_rag.providers.ollama import OllamaGenerator

            generator = OllamaGenerator(http("ollama"), settings.generation_model)
    chunker = CharacterChunker(settings.chunk_chars, settings.chunk_overlap, settings.max_chunks)
    signature = hashlib.sha256(
        f"extract-v1|pdf:{settings.module_pdf_enabled}|{chunker.signature}|{embedder.signature}|{settings.embedding_revision}".encode()
    ).hexdigest()
    repository = repository or SQLRepository(settings)
    reranker = None
    if settings.module_reranking_enabled:
        from forge_rag.reranking.lexical import LexicalReranker

        reranker = LexicalReranker()
    runtime = Runtime(
        settings,
        repository,
        QueryService(settings, repository, embedder, generator, signature, reranker),
        closers=closers,
    )
    if settings.module_ingestion_enabled:
        from forge_rag.ingestion.extraction import ExtractorRegistry, TextExtractor
        from forge_rag.ingestion.service import IngestionService
        from forge_rag.ingestion.worker import Worker

        text = TextExtractor()
        extractors: dict[str, Extractor] = {"text/plain": text, "text/markdown": text}
        if settings.module_pdf_enabled:
            from forge_rag.pdf.extractor import PDFExtractor

            extractors["application/pdf"] = PDFExtractor()
        runtime.ingestion = IngestionService(settings, repository, signature)
        runtime.worker = Worker(
            settings, repository, ExtractorRegistry(extractors), chunker, embedder, signature
        )
    return runtime
