import base64
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class IntegrationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="rag_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    module_enabled: bool = False
    url: str = "http://127.0.0.1:8090"
    issuer: str = "forge-fastapi"
    audience: str = "modular-forge-rag"
    delegation_key: SecretStr = SecretStr("")
    timeout_seconds: float = 90

    @model_validator(mode="after")
    def validate_enabled(self):
        if not self.module_enabled:
            return self
        parsed = urlparse(self.url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise ValueError("RAG_URL must be a fixed service origin")
        key = base64.b64decode(self.delegation_key.get_secret_value(), validate=True)
        if len(key) != 32 or len(set(key)) < 16:
            raise ValueError("RAG_DELEGATION_KEY must contain 32 random Base64 bytes")
        return self


@dataclass(frozen=True)
class RagIdentity:
    subject: str
    tenant: str
    groups: tuple[str, ...] = ()


def private_identity(account: dict, issuer: str):
    subject = str(account["id"])
    return RagIdentity(subject, f"personal:{issuer}:{subject}")


class RagGateway:
    def __init__(self, settings: IntegrationSettings, *, transport=None):
        self.settings, self.transport = settings, transport

    def token(self, identity: RagIdentity, scope: str):
        now = int(time.time())
        return jwt.encode(
            {
                "iss": self.settings.issuer,
                "sub": identity.subject,
                "tenant": identity.tenant,
                "groups": list(identity.groups),
                "scope": [scope],
                "aud": self.settings.audience,
                "iat": now,
                "nbf": now,
                "exp": now + 60,
                "jti": str(uuid.uuid4()),
                "type": "rag-delegation",
            },
            base64.b64decode(self.settings.delegation_key.get_secret_value(), validate=True),
            algorithm="HS256",
            headers={"typ": "rag-delegation+jwt"},
        )

    def forward(
        self, method: str, path: str, identity: RagIdentity, scope: str, *, payload=None, key=None
    ):
        headers = {"Authorization": "Bearer " + self.token(identity, scope)}
        if key is not None:
            headers["Idempotency-Key"] = key
        try:
            with httpx.Client(
                base_url=self.settings.url,
                timeout=self.settings.timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
            ) as client:
                result = client.request(method, path, json=payload, headers=headers)
            if result.status_code == 204:
                return Response(status_code=204)
            if not 200 <= result.status_code < 300:
                status = (
                    result.status_code
                    if result.status_code in {400, 403, 404, 409, 410, 413, 415, 422, 429}
                    else 503
                )
                return JSONResponse(
                    {
                        "error": {
                            "code": "rag_request_failed",
                            "message": "RAG request could not be completed.",
                        }
                    },
                    status_code=status,
                )
            return JSONResponse(result.json(), status_code=result.status_code)
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "RAG service is unavailable.") from exc


def install(
    app,
    settings: IntegrationSettings | None = None,
    *,
    account_dependency=None,
    identity_resolver=None,
    transport=None,
):
    settings = settings or IntegrationSettings()
    if not settings.module_enabled:
        return
    if account_dependency is None:
        from modular_forge.security.dependencies import current_account

        account_dependency = current_account
    identity_resolver = identity_resolver or (
        lambda account: private_identity(account, settings.issuer)
    )
    gateway = RagGateway(settings, transport=transport)
    router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])

    @router.post("/query")
    def query(payload: dict, account=Depends(account_dependency)):
        return gateway.forward(
            "POST", "/v1/query", identity_resolver(account), "rag:read", payload=payload
        )

    @router.post("/search")
    def search(payload: dict, account=Depends(account_dependency)):
        return gateway.forward(
            "POST", "/v1/search", identity_resolver(account), "rag:read", payload=payload
        )

    @router.post("/documents", status_code=202)
    def enqueue(
        payload: dict, idempotency_key: str = Header(...), account=Depends(account_dependency)
    ):
        return gateway.forward(
            "POST",
            "/v1/documents",
            identity_resolver(account),
            "rag:write",
            payload=payload,
            key=idempotency_key,
        )

    @router.get("/documents/{document_id}")
    def document(document_id: uuid.UUID, account=Depends(account_dependency)):
        return gateway.forward(
            "GET", f"/v1/documents/{document_id}", identity_resolver(account), "rag:read"
        )

    @router.delete("/documents/{document_id}", status_code=204)
    def delete(document_id: uuid.UUID, account=Depends(account_dependency)):
        return gateway.forward(
            "DELETE", f"/v1/documents/{document_id}", identity_resolver(account), "rag:write"
        )

    @router.get("/jobs/{job_id}")
    def job(job_id: uuid.UUID, account=Depends(account_dependency)):
        return gateway.forward("GET", f"/v1/jobs/{job_id}", identity_resolver(account), "rag:write")

    app.include_router(router)
