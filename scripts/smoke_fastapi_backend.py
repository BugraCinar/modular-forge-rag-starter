"""Real sibling FastAPI auth -> gateway -> Compose RAG smoke (fixture data only)."""

import base64
import secrets
import tempfile
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from forge_rag_integration import IntegrationSettings, install
from modular_forge.app import create_app
from modular_forge.shared.config import Settings as BackendSettings

from forge_rag.shared.config import Settings


def secret():
    return base64.b64encode(secrets.token_bytes(32)).decode()


rag_settings = Settings()
with tempfile.TemporaryDirectory(prefix="forge-backend-contract-") as temporary:
    settings = BackendSettings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{(Path(temporary) / 'backend.db').as_posix()}",
        auto_create_schema=True,
        jwt_secret=secret(),
        pepper=secret(),
        token_hash_secret=secret(),
        rate_limit_backend="memory",
        module_email_enabled=False,
        module_audit_enabled=False,
    )
    app = create_app(settings)
    install(
        app,
        IntegrationSettings(
            _env_file=None,
            module_enabled=True,
            delegation_key=rag_settings.delegation_keys["forge-fastapi"],
        ),
    )
    with TestClient(app) as client:
        runtime = app.state.runtime
        with runtime.database.transaction() as tx:
            account = tx.insert(
                "accounts",
                {
                    "id": str(uuid.uuid4()),
                    "email": "smoke@example.com",
                    "username": "smoke_user",
                    "password_hash": runtime.security.hash_password("Fixture-Only-Password-2026!"),
                    "role": "USER",
                    "active": True,
                    "verified": True,
                    "auth_version": 0,
                    "failed_logins": 0,
                    "locked_until": 0,
                    "created_at": int(time.time()),
                    "deactivated_at": None,
                },
            )
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "smoke_user", "password": "Fixture-Only-Password-2026!"},
        )
        assert login.status_code == 200, login.status_code
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        assert client.post("/api/v1/rag/query", json={"question": "Returns?"}).status_code == 401
        created = client.post(
            "/api/v1/rag/documents",
            headers={**headers, "Idempotency-Key": "real-backend-policy"},
            json={
                "external_id": "policy",
                "title": "Policy",
                "content": "Returns are accepted within 30 days.",
            },
        )
        assert created.status_code == 202, created.status_code
        job = created.json()
        deadline = time.monotonic() + 30
        while (
            client.get("/api/v1/rag/jobs/" + job["id"], headers=headers).json()["status"]
            != "completed"
        ):
            assert time.monotonic() < deadline
            time.sleep(0.5)
        answer = client.post("/api/v1/rag/query", headers=headers, json={"question": "Returns?"})
        assert answer.status_code == 200 and "30 days" in answer.json()["answer"]
        with runtime.database.transaction() as tx:
            current = tx.get("accounts", account["id"])
            tx.update("accounts", account["id"], {"auth_version": 1}, revision=current["revision"])
        assert (
            client.post(
                "/api/v1/rag/query", headers=headers, json={"question": "Returns?"}
            ).status_code
            == 401
        )
        # A new current token is needed even for deletion after invalidating the old session.
        refreshed = client.post(
            "/api/v1/auth/login",
            json={"username": "smoke_user", "password": "Fixture-Only-Password-2026!"},
        )
        assert refreshed.status_code == 200
        headers = {"Authorization": "Bearer " + refreshed.json()["access_token"]}
        assert (
            client.delete(
                "/api/v1/rag/documents/" + job["document_id"], headers=headers
            ).status_code
            == 204
        )
print("Real FastAPI login, gateway, RAG answer, auth-version revocation and deletion passed.")
