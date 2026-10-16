import unicodedata

from forge_rag.shared.errors import InvalidDocument
from forge_rag.shared.models import Section


class TextExtractor:
    def extract(self, content: str, media_type: str) -> list[Section]:
        if media_type not in {"text/plain", "text/markdown"}:
            raise InvalidDocument("Unsupported media type")
        text = unicodedata.normalize("NFC", content.replace("\r\n", "\n").replace("\r", "\n"))
        if "\x00" in text or not text.strip():
            raise InvalidDocument("Empty or binary document")
        return [Section(text.strip())]


class ExtractorRegistry:
    def __init__(self, extractors):
        self.extractors = extractors

    def extract(self, content: str, media_type: str):
        extractor = self.extractors.get(media_type)
        if extractor is None:
            raise InvalidDocument("Extractor is disabled")
        return extractor.extract(content, media_type)
