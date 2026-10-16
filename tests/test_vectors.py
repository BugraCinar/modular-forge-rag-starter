import pytest

from forge_rag.shared.errors import ProviderError, RagError
from forge_rag.shared.models import QueryInput
from forge_rag.shared.vectors import validate_vectors


@pytest.mark.parametrize(
    "value",
    [
        [],
        [[0.0] * 16],
        [[float("nan")] * 16],
        [[float("inf")] * 16],
        [[True] * 16],
        [["bad"] * 16],
        [[1.0] * 15],
        "not-vectors",
    ],
)
def test_malformed_provider_vectors(value):
    with pytest.raises(ProviderError):
        validate_vectors(value, 1, 16)


def test_query_bad_provider_is_generic_503(service, account):
    runtime, _ = service

    class BadEmbedder:
        dimensions = 256
        signature = "bad"

        def embed(self, texts):
            return [["provider-secret"] * 256]

    runtime.query.embedder = BadEmbedder()
    with pytest.raises(RagError) as exc:
        runtime.query.answer(account, QueryInput(question="Returns?"))
    assert exc.value.status == 503
    assert "provider-secret" not in exc.value.message
