import json

import httpx
import pytest

from forge_rag.providers.http import ProviderHTTP
from forge_rag.providers.ollama import OllamaEmbedder, OllamaGenerator
from forge_rag.providers.openai import OpenAIEmbedder, OpenAIGenerator
from forge_rag.shared.errors import ProviderError
from forge_rag.shared.models import Hit


def hit():
    return Hit("chunk-1", "doc-1", 1, "Title", "Returns in 30 days.", 0, None, 0, 19)


def test_openai_embedding_and_structured_responses():
    def handle(request):
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer fixture-key"
        if request.url.path.endswith("embeddings"):
            assert payload["dimensions"] == 16 and payload["encoding_format"] == "float"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": 1, "embedding": [2.0] * 16},
                        {"index": 0, "embedding": [1.0] * 16},
                    ]
                },
            )
        assert payload["store"] is False and payload["text"]["format"]["strict"] is True
        assert json.loads(payload["input"])["evidence"][0]["chunk_id"] == "chunk-1"
        text = json.dumps({"statements": [{"text": "30 days", "chunk_ids": ["chunk-1"]}]})
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            },
        )

    http = ProviderHTTP(
        "https://api.openai.com/v1", 10, key="fixture-key", transport=httpx.MockTransport(handle)
    )
    try:
        assert OpenAIEmbedder(http, "configured-model", 16).embed(["one", "two"])[0] == [1.0] * 16
        generated = OpenAIGenerator(http, "configured-model").generate("Returns?", [hit()])
        assert generated.content.statements[0].chunk_ids == ["chunk-1"]
        assert generated.usage["total_tokens"] == 15
    finally:
        http.close()


def test_ollama_provider_contract():
    def handle(request):
        payload = json.loads(request.content)
        if request.url.path.endswith("embed"):
            assert payload["truncate"] is False
            return httpx.Response(200, json={"embeddings": [[1.0] * 16]})
        assert payload["stream"] is False and payload["format"]["type"] == "object"
        return httpx.Response(
            200,
            json={
                "done": True,
                "response": '{"statements":[{"text":"30 days","chunk_ids":["chunk-1"]}]}',
                "eval_count": 3,
            },
        )

    http = ProviderHTTP("http://localhost:11434", 10, transport=httpx.MockTransport(handle))
    try:
        assert len(OllamaEmbedder(http, "embedding", 16).embed(["Returns"])[0]) == 16
        assert (
            OllamaGenerator(http, "generation").generate("Returns?", [hit()]).usage["output_tokens"]
            == 3
        )
    finally:
        http.close()


@pytest.mark.parametrize("status", [302, 401, 429, 500])
def test_provider_failures_do_not_expose_payloads(status):
    http = ProviderHTTP(
        "https://example.invalid",
        1,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, text="sensitive upstream diagnostic")
        ),
    )
    try:
        with pytest.raises(ProviderError) as exc:
            http.post("responses", {})
        assert "sensitive" not in str(exc.value)
    finally:
        http.close()


def test_incomplete_generation_is_not_used():
    http = ProviderHTTP(
        "https://example.invalid",
        1,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "incomplete", "output": []})
        ),
    )
    try:
        with pytest.raises(ProviderError):
            OpenAIGenerator(http, "configured").generate("Question", [hit()])
    finally:
        http.close()
