import base64
import time

import jwt
import pytest
from pydantic import ValidationError

from forge_rag.security.delegation import issue_token
from forge_rag.shared.config import Settings
from forge_rag.shared.models import Principal
from tests.conftest import KEY, auth


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "unknown"},
        {"aud": "wrong-service"},
        {"type": "access"},
        {"exp": 1},
        {"exp": int(time.time()) + 3600},
        {"tenant": ""},
        {"groups": "admin"},
        {"scope": ["rag:superadmin"]},
        {"sub": 123},
        {"iat": "today"},
    ],
)
def test_invalid_delegations(service, account, change):
    _, client = service
    claims = jwt.decode(issue_token(KEY, account), options={"verify_signature": False})
    claims.update(change)
    token = jwt.encode(claims, KEY, algorithm="HS256", headers={"typ": "rag-delegation+jwt"})
    result = client.get("/v1/modules", headers={"Authorization": "Bearer " + token})
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "unauthorized"


def test_missing_signature_or_wrong_signing_key(service, account):
    _, client = service
    assert client.get("/v1/modules").status_code == 401
    assert (
        client.get(
            "/v1/modules",
            headers={"Authorization": "Bearer " + issue_token(bytes(range(32, 64)), account)},
        ).status_code
        == 401
    )
    token = jwt.encode({"iss": "forge-fastapi"}, "", algorithm="none")
    assert (
        client.get("/v1/modules", headers={"Authorization": "Bearer " + token}).status_code == 401
    )


def test_scope_and_client_context_spoofing(service, account):
    _, client = service
    reader = Principal(account.issuer, account.subject, account.tenant, scopes=("rag:read",))
    assert (
        client.post(
            "/v1/documents",
            headers={**auth(reader), "Idempotency-Key": "key"},
            json={"external_id": "x", "title": "x", "content": "x"},
        ).status_code
        == 403
    )
    result = client.post(
        "/v1/query", headers=auth(account), json={"question": "Private secret", "tenant": "another"}
    )
    assert result.status_code == 422
    assert "Private secret" not in result.text


def test_bounded_request_and_generic_validation(service, account):
    runtime, client = service
    result = client.post(
        "/v1/query",
        headers=auth(account),
        content=b"x" * (runtime.settings.max_document_bytes * 2 + 20000),
    )
    assert result.status_code == 413
    assert result.headers["x-content-type-options"] == "nosniff"
    result = client.post("/v1/query", headers=auth(account), json={"question": ""})
    assert result.status_code == 422 and "input" not in result.text


def test_health_headers_and_host(service):
    _, client = service
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/health/live", headers={"Host": "attacker.invalid"}).status_code == 400


def test_no_usable_default_key_and_distinct_keys():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, delegation_keys={})
    with pytest.raises(ValidationError):
        Settings(_env_file=None, delegation_keys={"a": base64.b64encode(b"x" * 32).decode()})
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            delegation_keys={
                "a": base64.b64encode(KEY).decode(),
                "b": base64.b64encode(KEY).decode(),
            },
        )


def test_production_configuration_fails_closed(settings):
    values = settings.model_dump()
    values["environment"] = "production"
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(_env_file=None, **values)
    values["database_url"] = "postgresql+psycopg://localhost/forge"
    with pytest.raises(ValidationError, match="API docs"):
        Settings(_env_file=None, **values)


def test_document_limits_and_disabled_pdf(service, account):
    _, client = service
    headers = {**auth(account), "Idempotency-Key": "large"}
    result = client.post(
        "/v1/documents",
        headers=headers,
        json={"external_id": "large", "title": "Large", "content": "ş" * 600000},
    )
    assert result.status_code == 413
    result = client.post(
        "/v1/documents",
        headers=headers,
        json={
            "external_id": "pdf",
            "title": "PDF",
            "content": "JVBERi0=",
            "media_type": "application/pdf",
        },
    )
    assert result.status_code == 415
