from dataclasses import replace

import pytest
from sqlalchemy import select

from forge_rag.evaluation.runner import evaluate
from forge_rag.shared.errors import RagError
from forge_rag.shared.models import (
    DocumentInput,
    Generated,
    Generation,
    Principal,
    QueryInput,
    Statement,
)
from tests.conftest import auth, ingest


def test_full_http_pipeline(service, account):
    runtime, client = service
    headers = {**auth(account), "Idempotency-Key": "policy-v1"}
    result = client.post(
        "/v1/documents",
        headers=headers,
        json={
            "external_id": "policy",
            "title": "Returns",
            "content": "Returns are accepted within 30 days.",
        },
    )
    assert result.status_code == 202
    job = result.json()
    assert (
        client.post("/v1/query", headers=auth(account), json={"question": "Returns?"}).json()[
            "status"
        ]
        == "insufficient_evidence"
    )
    assert runtime.worker.once()
    assert (
        client.get("/v1/jobs/" + job["id"], headers=auth(account)).json()["status"] == "completed"
    )
    answer = client.post("/v1/query", headers=auth(account), json={"question": "Returns?"}).json()
    assert answer["status"] == "answered"
    assert "30 days" in answer["answer"]
    assert answer["citations"][0]["document_id"] == job["document_id"]
    assert answer["statements"][0]["chunk_ids"] == [answer["citations"][0]["chunk_id"]]
    assert (
        client.get("/v1/documents/" + job["document_id"], headers=auth(account)).json()[
            "active_revision"
        ]
        == 1
    )
    with runtime.repository.engine.connect() as connection:
        assert connection.execute(select(runtime.repository.jobs.c.payload)).scalar_one() == {}


@pytest.mark.parametrize(
    "reader",
    [
        Principal("forge-fastapi", "bob", "tenant-a"),
        Principal("forge-fastapi", "alice", "tenant-b"),
        Principal("forge-spring", "alice", "tenant-a"),
    ],
)
def test_private_document_isolation(service, account, reader):
    runtime, client = service
    job = ingest(runtime, account)
    assert (
        client.post("/v1/search", headers=auth(reader), json={"question": "Returns"}).json()[
            "matches"
        ]
        == []
    )
    assert (
        client.get("/v1/documents/" + job["document_id"], headers=auth(reader)).status_code == 404
    )
    assert client.get("/v1/jobs/" + job["id"], headers=auth(reader)).status_code == 404
    assert (
        client.delete("/v1/documents/" + job["document_id"], headers=auth(reader)).status_code
        == 404
    )


def test_acl_applied_before_candidate_selection(service, account):
    runtime, _ = service
    bob = replace(account, subject="bob")
    ingest(
        runtime,
        account,
        external_id="secret",
        text="".join(["Secret budget returns 999 million. "] * 100),
        key="secret",
    )
    public = ingest(
        runtime,
        account,
        external_id="shared",
        text="Returns are accepted for 30 days.",
        key="shared",
        read_subjects=[bob.actor],
    )
    hits = runtime.query.retrieve(bob, QueryInput(question="Returns budget", top_k=1))
    assert len(hits) == 1
    assert hits[0].document_id == public["document_id"]
    assert "999" not in hits[0].text


def test_group_acl_and_tenant_boundary(service, account):
    runtime, _ = service
    ingest(runtime, account, read_groups=["support"])
    bob = replace(account, subject="bob", groups=("support",))
    assert runtime.query.retrieve(bob, QueryInput(question="Returns"))
    assert (
        runtime.query.retrieve(replace(bob, tenant="other"), QueryInput(question="Returns")) == []
    )


def test_dataset_boundary(service, account):
    runtime, _ = service
    ingest(runtime, account, dataset="private-dataset")
    assert runtime.query.retrieve(account, QueryInput(question="Returns")) == []
    assert runtime.query.retrieve(
        account, QueryInput(question="Returns", dataset="private-dataset")
    )


def test_idempotency_conflict_and_update(service, account):
    runtime, _ = service
    first = ingest(runtime, account)
    request = DocumentInput(
        external_id="policy", title="Policy", content="Returns are accepted within 30 days."
    )
    assert runtime.ingestion.enqueue(account, request, "document-1")["id"] == first["id"]
    with pytest.raises(RagError, match="different request"):
        runtime.ingestion.enqueue(
            account, request.model_copy(update={"content": "New content"}), "document-1"
        )
    second = runtime.ingestion.enqueue(
        account,
        request.model_copy(update={"content": "Returns are accepted within 60 days."}),
        "document-2",
    )
    assert second["document_id"] == first["document_id"] and second["revision"] == 2
    assert runtime.query.retrieve(account, QueryInput(question="Returns")) == []
    runtime.worker.once()
    assert "60 days" in runtime.query.answer(account, QueryInput(question="Returns"))["answer"]


def test_owner_cannot_be_overwritten_by_reader(service, account):
    runtime, _ = service
    bob = replace(account, subject="bob")
    ingest(runtime, account, read_subjects=[bob.actor])
    with pytest.raises(RagError):
        runtime.ingestion.enqueue(
            bob, DocumentInput(external_id="policy", title="Stolen", content="No"), "steal"
        )


def test_delete_removes_all_data_and_blocks_old_idempotency_key(service, account):
    runtime, client = service
    job = ingest(runtime, account)
    assert (
        client.delete("/v1/documents/" + job["document_id"], headers=auth(account)).status_code
        == 204
    )
    assert runtime.query.retrieve(account, QueryInput(question="Returns")) == []
    with runtime.repository.engine.connect() as connection:
        assert connection.execute(select(runtime.repository.chunks)).all() == []
        assert connection.execute(select(runtime.repository.jobs.c.payload)).scalar_one() == {}
    with pytest.raises(RagError) as exc:
        ingest(runtime, account)
    assert exc.value.status == 410


def test_unknown_citation_rejected(service, account):
    runtime, _ = service
    ingest(runtime, account)

    class BadGenerator:
        def generate(self, question, hits):
            return Generated(
                Generation(statements=[Statement(text="Made up", chunk_ids=["not-retrieved"])])
            )

    runtime.query.generator = BadGenerator()
    with pytest.raises(RagError) as exc:
        runtime.query.answer(account, QueryInput(question="Returns"))
    assert exc.value.code == "invalid_citation"


def test_access_rechecked_after_generation(service, account):
    runtime, _ = service
    job = ingest(runtime, account)

    class RevokingGenerator:
        def generate(self, question, hits):
            runtime.repository.delete(account, job["document_id"])
            return Generated(
                Generation(statements=[Statement(text="Returns", chunk_ids=[hits[0].id])])
            )

    runtime.query.generator = RevokingGenerator()
    with pytest.raises(RagError) as exc:
        runtime.query.answer(account, QueryInput(question="Returns"))
    assert exc.value.code == "context_changed"


def test_embedding_signature_filters_old_index(service, account):
    runtime, _ = service
    ingest(runtime, account)
    runtime.query.signature = "different-model"
    assert runtime.query.retrieve(account, QueryInput(question="Returns")) == []


def test_context_budget(service, account):
    runtime, _ = service
    for number in range(10):
        ingest(
            runtime,
            account,
            external_id=f"d{number}",
            key=f"k{number}",
            text="Returns policy. " * 100,
        )
    hits = runtime.query.retrieve(account, QueryInput(question="Returns", top_k=10))
    assert sum(len(hit.text) for hit in hits) <= runtime.settings.max_context_chars


def test_offline_evaluation():
    assert all(value == 1 for value in evaluate()["metrics"].values())
