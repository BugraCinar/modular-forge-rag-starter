import base64
import json

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from forge_rag_integration import IntegrationSettings, install

from forge_rag.security.delegation import verify_token
from tests.conftest import KEY


def config():
    return IntegrationSettings(
        _env_file=None, module_enabled=True, delegation_key=base64.b64encode(KEY).decode()
    )


def test_backend_authentication_then_least_privilege_delegation(settings):
    captured = []

    def current_account(authorization: str = Header("")):
        if authorization != "Bearer valid-current-account":
            raise HTTPException(401)
        return {"id": "account-42", "role": "USER"}

    def upstream(request):
        principal = verify_token(settings, request.headers["authorization"].removeprefix("Bearer "))
        captured.append(principal)
        assert request.url.path == "/v1/query"
        assert json.loads(request.content) == {"question": "Returns?"}
        return httpx.Response(200, json={"status": "answered", "answer": "30 days"})

    app = FastAPI()
    install(
        app, config(), account_dependency=current_account, transport=httpx.MockTransport(upstream)
    )
    with TestClient(app) as client:
        assert client.post("/api/v1/rag/query", json={"question": "Returns?"}).status_code == 401
        assert not captured
        result = client.post(
            "/api/v1/rag/query",
            headers={"Authorization": "Bearer valid-current-account"},
            json={"question": "Returns?"},
        )
        assert result.status_code == 200
        assert captured[0].tenant == "personal:forge-fastapi:account-42"
        assert captured[0].scopes == ("rag:read",)


def test_disabled_integration_needs_no_secret():
    app = FastAPI()
    install(app, IntegrationSettings(_env_file=None, module_enabled=False))
    with TestClient(app) as client:
        assert client.post("/api/v1/rag/query", json={}).status_code == 404


def test_ingestion_status_key_and_delete_preserved(settings):
    def upstream(request):
        principal = verify_token(settings, request.headers["authorization"].removeprefix("Bearer "))
        assert principal.scopes == ("rag:write",)
        if request.method == "DELETE":
            return httpx.Response(204)
        assert request.headers["idempotency-key"] == "document-1"
        return httpx.Response(202, json={"id": "job", "status": "queued"})

    app = FastAPI()
    install(
        app,
        config(),
        account_dependency=lambda: {"id": "42"},
        transport=httpx.MockTransport(upstream),
    )
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/rag/documents", headers={"Idempotency-Key": "document-1"}, json={}
            ).status_code
            == 202
        )
        assert (
            client.delete("/api/v1/rag/documents/00000000-0000-0000-0000-000000000001").status_code
            == 204
        )
        assert client.delete("/api/v1/rag/documents/..%2F..%2Fadmin").status_code in {404, 422}
