import base64
import re

from forge_rag.shared.config import Settings
from forge_rag.shared.errors import RagError
from forge_rag.shared.models import DocumentInput, Principal
from forge_rag.shared.ports import Repository


class IngestionService:
    def __init__(self, settings: Settings, repository: Repository, signature: str):
        self.settings, self.repository, self.signature = settings, repository, signature

    def enqueue(self, principal: Principal, request: DocumentInput, key: str):
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,128}", key):
            raise RagError(
                422, "invalid_idempotency_key", "Supply a 1-128 character Idempotency-Key."
            )
        if any(not 1 <= len(value) <= 200 for value in request.read_subjects + request.read_groups):
            raise RagError(422, "invalid_acl", "ACL entries must contain 1-200 characters.")
        if any(":" not in subject for subject in request.read_subjects):
            raise RagError(422, "invalid_acl", "Subjects must use the issuer:subject namespace.")
        if request.media_type == "application/pdf":
            if not self.settings.module_pdf_enabled:
                raise RagError(415, "extractor_disabled", "PDF extraction is disabled.")
            try:
                raw = base64.b64decode(request.content, validate=True)
            except ValueError as exc:
                raise RagError(422, "invalid_pdf", "PDF content must be Base64.") from exc
            if not raw.startswith(b"%PDF-"):
                raise RagError(422, "invalid_pdf", "Invalid PDF signature.")
        else:
            raw = request.content.encode("utf-8")
        if len(raw) > self.settings.max_document_bytes:
            raise RagError(413, "document_too_large", "Document exceeds the byte limit.")
        return self.repository.enqueue(principal, request, key, self.signature)
