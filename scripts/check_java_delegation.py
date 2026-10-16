"""Run immediately after Java tests; the public fixture JWT expires in 60 seconds."""

import base64
from pathlib import Path

from forge_rag.security.delegation import verify_token
from forge_rag.shared.config import Settings

settings = Settings(
    _env_file=None,
    delegation_keys={"forge-spring": base64.b64encode(bytes(range(32, 64))).decode()},
)
token = Path("integrations/spring-boot/target/python-contract.jwt").read_text(encoding="utf-8")
principal = verify_token(settings, token)
assert principal.subject == "user:42"
assert principal.tenant == "personal:forge-spring:user:42"
assert principal.scopes == ("rag:read",)
print("Java delegation verified by the Python RAG service.")
