import base64
import io

from pypdf import PdfReader

from forge_rag.shared.errors import InvalidDocument
from forge_rag.shared.models import Section


class PDFExtractor:
    def extract(self, content: str, media_type: str) -> list[Section]:
        try:
            reader = PdfReader(io.BytesIO(base64.b64decode(content, validate=True)), strict=True)
            if reader.is_encrypted or len(reader.pages) > 100:
                raise InvalidDocument("Encrypted or oversized PDF")
            sections = []
            total = 0
            for number, page in enumerate(reader.pages, start=1):
                stream = page.get_contents()
                if stream is not None and len(stream.get_data()) > 5_000_000:
                    raise InvalidDocument("PDF stream exceeds limit")
                value = page.extract_text() or ""
                total += len(value)
                if total > 1_000_000:
                    raise InvalidDocument("Extracted PDF exceeds limit")
                if value.strip():
                    sections.append(Section(value.strip(), number))
            if not sections:
                raise InvalidDocument("PDF has no text layer; OCR is required")
            return sections
        except InvalidDocument:
            raise
        except Exception as exc:
            raise InvalidDocument("Invalid PDF") from exc
