from forge_rag.providers.http import (
    INSTRUCTIONS,
    ProviderHTTP,
    evidence,
    output_schema,
    parse_generation,
)
from forge_rag.shared.errors import ProviderError
from forge_rag.shared.models import Generated, Hit


class OpenAIEmbedder:
    def __init__(self, http: ProviderHTTP, model: str, dimensions: int):
        self.http, self.model, self.dimensions = http, model, dimensions
        self.signature = f"openai:{model}:{dimensions}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self.http.post(
            "embeddings",
            {
                "model": self.model,
                "input": texts,
                "encoding_format": "float",
                "dimensions": self.dimensions,
            },
        )
        try:
            rows = sorted(result["data"], key=lambda row: row["index"])
            if [row["index"] for row in rows] != list(range(len(texts))):
                raise ValueError("Missing embedding")
            return [row["embedding"] for row in rows]
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Invalid embedding response") from exc


class OpenAIGenerator:
    def __init__(self, http: ProviderHTTP, model: str):
        self.http, self.model = http, model

    def generate(self, question: str, hits: list[Hit]) -> Generated:
        result = self.http.post(
            "responses",
            {
                "model": self.model,
                "store": False,
                "instructions": INSTRUCTIONS,
                "input": evidence(question, hits),
                "max_output_tokens": 1200,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "grounded_answer",
                        "strict": True,
                        "schema": output_schema(),
                    }
                },
            },
        )
        try:
            if result.get("status") != "completed":
                raise ProviderError("Incomplete generation")
            parts = [
                part["text"]
                for item in result["output"]
                if item.get("type") == "message"
                for part in item.get("content", [])
                if part.get("type") == "output_text"
            ]
            if not parts:
                return Generated(parse_generation('{"statements":[]}'))
            usage = result.get("usage", {})
            return Generated(
                parse_generation("".join(parts)),
                {
                    name: int(usage.get(name, 0))
                    for name in ("input_tokens", "output_tokens", "total_tokens")
                },
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Invalid generation response") from exc
