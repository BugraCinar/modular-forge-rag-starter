import math

from forge_rag.shared.errors import ProviderError


def validate_vectors(values: list[list[float]], count: int, dimensions: int) -> list[list[float]]:
    if not isinstance(values, list) or len(values) != count:
        raise ProviderError("Invalid embedding count")
    for vector in values:
        if not isinstance(vector, list) or len(vector) != dimensions:
            raise ProviderError("Invalid embedding dimensions")
        if any(
            type(value) not in {float, int} or not math.isfinite(value) for value in vector
        ) or not any(vector):
            raise ProviderError("Invalid embedding values")
    return values
