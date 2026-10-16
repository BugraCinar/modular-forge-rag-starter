from dataclasses import asdict

from forge_rag.shared.config import Settings
from forge_rag.shared.errors import ProviderError, RagError
from forge_rag.shared.models import Principal, QueryInput
from forge_rag.shared.ports import Embedder, Generator, Repository, Reranker
from forge_rag.shared.vectors import validate_vectors


class QueryService:
    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        embedder: Embedder,
        generator: Generator,
        signature: str,
        reranker: Reranker | None = None,
    ):
        self.settings, self.repository, self.embedder = settings, repository, embedder
        self.generator, self.signature, self.reranker = generator, signature, reranker

    def retrieve(self, principal: Principal, request: QueryInput):
        if not request.question.strip():
            raise RagError(422, "empty_question", "Question must contain text.")
        try:
            vectors = validate_vectors(
                self.embedder.embed([request.question]), 1, self.embedder.dimensions
            )
            hits = self.repository.search(
                principal,
                request.dataset,
                self.signature,
                vectors[0],
                request.question,
                self.settings.candidate_limit,
            )
            hits = [
                hit
                for hit in hits
                if hit.similarity >= self.settings.min_similarity or hit.lexical > 0
            ]
            if self.reranker is not None:
                hits = self.reranker.rank(request.question, hits)
            selected, size = [], 0
            for hit in hits[: request.top_k]:
                if size + len(hit.text) <= self.settings.max_context_chars:
                    selected.append(hit)
                    size += len(hit.text)
            return selected
        except ProviderError as exc:
            raise RagError(
                503, "provider_unavailable", "Embedding provider is unavailable."
            ) from exc

    def search(self, principal: Principal, request: QueryInput):
        return {"matches": [asdict(hit) for hit in self.retrieve(principal, request)]}

    def answer(self, principal: Principal, request: QueryInput):
        hits = self.retrieve(principal, request)
        if not hits:
            return {
                "status": "insufficient_evidence",
                "answer": "",
                "statements": [],
                "citations": [],
                "usage": {},
            }
        try:
            generated = self.generator.generate(request.question, hits)
        except ProviderError as exc:
            raise RagError(
                503, "provider_unavailable", "Generation provider is unavailable."
            ) from exc
        available = {hit.id: hit for hit in hits}
        used = set()
        for statement in generated.content.statements:
            if not set(statement.chunk_ids) <= available.keys():
                raise RagError(502, "invalid_citation", "Provider returned an unknown citation.")
            used.update(statement.chunk_ids)
        if not self.repository.still_allowed(principal, list(available)):
            raise RagError(
                409, "context_changed", "Evidence changed during generation; retry the question."
            )
        citations = [
            dict(
                chunk_id=hit.id,
                document_id=hit.document_id,
                title=hit.title,
                revision=hit.revision,
                page=hit.page,
                start=hit.start,
                end=hit.end,
                excerpt=hit.text,
            )
            for hit in hits
            if hit.id in used
        ]
        statements = [statement.model_dump() for statement in generated.content.statements]
        return {
            "status": "answered" if statements else "insufficient_evidence",
            "answer": "\n".join(statement["text"] for statement in statements),
            "statements": statements,
            "citations": citations,
            "usage": generated.usage,
        }
