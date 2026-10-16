class RagError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class ProviderError(Exception):
    """Transient provider failure; diagnostic payloads must not be persisted."""


class InvalidDocument(Exception):
    """Permanent extraction or chunking failure."""
