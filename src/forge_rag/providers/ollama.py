from forge_rag.providers.http import (
    INSTRUCTIONS,
    ProviderHTTP,
    evidence,
    output_schema,
    parse_generation,
)
from forge_rag.shared.errors import ProviderError
from forge_rag.shared.models import Generated, Hit


class OllamaEmbedder:
    def __init__(self, http: ProviderHTTP, model: str, dimensions: int):
        self.http, self.model, self.dimensions = http, model, dimensions
        self.signature = f"ollama:{model}:{dimensions}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self.http.post(
            "api/embed", {"model": self.model, "input": texts, "truncate": False}
        )
        try:
            return result["embeddings"]
        except (KeyError, TypeError) as exc:
            raise ProviderError("Invalid embedding response") from exc


class OllamaGenerator:
    def __init__(self, http: ProviderHTTP, model: str):
        self.http, self.model = http, model

    def generate(self, question: str, hits: list[Hit]) -> Generated:
        result = self.http.post(
            "api/generate",
            {
                "model": self.model,
                "system": INSTRUCTIONS,
                "prompt": evidence(question, hits),
                "format": output_schema(),
                "stream": False,
                "options": {"num_predict": 1200, "temperature": 0},
            },
        )
        try:
            if not result.get("done"):
                raise ProviderError("Incomplete generation")
            usage = {
                "input_tokens": int(result.get("prompt_eval_count", 0)),
                "output_tokens": int(result.get("eval_count", 0)),
            }
            return Generated(parse_generation(result["response"]), usage)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Invalid generation response") from exc
