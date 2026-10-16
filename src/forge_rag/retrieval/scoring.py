import math
import re
from collections import Counter

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "what",
        "when",
        "how",
        "does",
        "do",
        "of",
        "to",
        "and",
        "for",
        "in",
        "on",
        "at",
        "with",
        "it",
        "bu",
        "bir",
        "ve",
        "ile",
        "ne",
        "nasıl",
        "için",
        "mi",
        "mı",
        "mu",
        "mü",
    }
)


def query_terms(text: str) -> list[str]:
    return [term for term in terms(text) if term not in STOP_WORDS]


def terms(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions differ")
    denominator = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator if denominator else 0


def bm25(question: str, texts: list[str]) -> list[float]:
    corpus = [Counter(terms(text)) for text in texts]
    average = sum(map(lambda item: sum(item.values()), corpus)) / max(len(corpus), 1)
    query = set(query_terms(question))
    frequencies = {term: sum(term in doc for doc in corpus) for term in query}
    result = []
    for doc in corpus:
        score = 0.0
        for term in query:
            count = doc[term]
            if count:
                inverse = math.log(
                    1 + (len(corpus) - frequencies[term] + 0.5) / (frequencies[term] + 0.5)
                )
                score += (
                    inverse
                    * count
                    * 2.2
                    / (count + 1.2 * (0.25 + 0.75 * sum(doc.values()) / max(average, 1)))
                )
        result.append(score)
    return result
