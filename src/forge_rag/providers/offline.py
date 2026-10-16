import hashlib
import math
import re

from forge_rag.retrieval.scoring import terms
from forge_rag.shared.models import Generated, Generation, Hit, Statement


class HashEmbedder:
    """Deterministic lexical fixture, not a semantic embedding model."""

    def __init__(self, dimensions: int):
        self.dimensions = dimensions
        self.signature = f"hash-v1:{dimensions}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for term in terms(text):
                digest = hashlib.sha256(term.encode()).digest()
                vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1
            norm = math.sqrt(sum(value * value for value in vector))
            if norm == 0:
                vector[0], norm = 1, 1
            result.append([value / norm for value in vector])
        return result


class ExtractiveGenerator:
    def generate(self, question: str, hits: list[Hit]) -> Generated:
        query = set(terms(question))
        candidates = [
            (len(query & set(terms(sentence))), sentence.strip(), hit.id)
            for hit in hits
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", hit.text)
            if sentence.strip()
        ]
        candidates.sort(key=lambda value: -value[0])
        statements = [
            Statement(text=sentence[:2000], chunk_ids=[identifier])
            for overlap, sentence, identifier in candidates[:3]
            if overlap
        ]
        return Generated(Generation(statements=statements))
