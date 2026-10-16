from forge_rag.shared.errors import InvalidDocument
from forge_rag.shared.models import Piece, Section


class CharacterChunker:
    def __init__(self, size: int, overlap: int, maximum: int):
        self.size, self.overlap, self.maximum = size, overlap, maximum
        self.signature = f"chars-v1:{size}:{overlap}"

    def split(self, sections: list[Section]) -> list[Piece]:
        pieces: list[Piece] = []
        for section in sections:
            start = 0
            while start < len(section.text):
                end = min(start + self.size, len(section.text))
                if end < len(section.text):
                    for separator in ("\n\n", "\n", ". ", " "):
                        boundary = section.text.rfind(separator, start + self.size // 2, end)
                        if boundary != -1:
                            end = boundary + len(separator)
                            break
                value = section.text[start:end]
                if value.strip():
                    pieces.append(Piece(value, len(pieces), start, end, section.page))
                if len(pieces) > self.maximum:
                    raise InvalidDocument("Document exceeds chunk limit")
                if end == len(section.text):
                    break
                start = max(start + 1, end - self.overlap)
        if not pieces:
            raise InvalidDocument("No extractable content")
        return pieces
