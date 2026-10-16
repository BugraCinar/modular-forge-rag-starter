"""Offline-provider HTTP/worker smoke against the local Compose deployment."""

import time
import uuid

import httpx

from forge_rag.security.delegation import issue_token
from forge_rag.shared.config import Settings
from forge_rag.shared.models import Principal

settings = Settings()
account = Principal("forge-fastapi", "smoke", "smoke-" + str(uuid.uuid4()))
with httpx.Client(base_url="http://127.0.0.1:8090", timeout=10) as client:
    deadline = time.monotonic() + 60
    while True:
        try:
            if client.get("/health/ready").status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError("RAG API did not become ready")
        time.sleep(1)

    def headers():
        return {"Authorization": "Bearer " + issue_token(settings.key(account.issuer), account)}

    response = client.post(
        "/v1/documents",
        headers={**headers(), "Idempotency-Key": "http-smoke-1"},
        json={
            "external_id": "policy",
            "title": "Returns",
            "content": "Returns are accepted within 30 days.",
        },
    )
    assert response.status_code == 202, response.status_code
    job = response.json()
    deadline = time.monotonic() + 30
    while True:
        status = client.get("/v1/jobs/" + job["id"], headers=headers()).json()["status"]
        if status == "completed":
            break
        assert status not in {"failed", "deleted", "superseded"}, status
        assert time.monotonic() < deadline, "Worker did not complete ingestion"
        time.sleep(0.5)
    answer = client.post("/v1/query", headers=headers(), json={"question": "Returns?"})
    assert answer.status_code == 200, answer.status_code
    assert "30 days" in answer.json()["answer"]
    assert answer.json()["citations"][0]["document_id"] == job["document_id"]
    assert (
        client.delete("/v1/documents/" + job["document_id"], headers=headers()).status_code == 204
    )
    assert (
        client.post("/v1/query", headers=headers(), json={"question": "Returns?"}).json()["status"]
        == "insufficient_evidence"
    )
print("HTTP -> durable worker -> retrieval -> cited answer -> deletion passed.")
