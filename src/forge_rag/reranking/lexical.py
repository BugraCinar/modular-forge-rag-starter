from forge_rag.retrieval.scoring import terms
from forge_rag.shared.models import Hit


class LexicalReranker:
    """Small deterministic adapter; replace the port with a cross-encoder if needed."""

    def rank(self, question: str, hits: list[Hit]) -> list[Hit]:
        query = set(terms(question))
        return sorted(
            hits, key=lambda hit: (-len(query & set(terms(hit.text))), -hit.score, hit.id)
        )
