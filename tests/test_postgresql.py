import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from forge_rag.persistence.store import SQLRepository
from forge_rag.runtime import build_runtime
from forge_rag.shared.models import DocumentInput, Principal, QueryInput
from tests.conftest import ingest


@pytest.mark.skipif(
    not os.environ.get("CONTRACT_DATABASE_URL"), reason="PostgreSQL/pgvector service required"
)
def test_pgvector_filtered_hybrid_and_concurrent_jobs(settings):
    settings.database_url = os.environ["CONTRACT_DATABASE_URL"]
    repository = SQLRepository(settings)
    repository.migrate()
    runtime = build_runtime(settings, repository=repository)
    alice = Principal("forge-fastapi", "alice", "contract-" + str(uuid.uuid4()))
    bob = Principal("forge-spring", "user:42", alice.tenant)
    try:
        ingest(
            runtime,
            alice,
            external_id="secret",
            key="secret",
            text="Returns budget confidential million " * 100,
        )
        shared = ingest(
            runtime,
            alice,
            external_id="shared",
            key="shared",
            text="Returns are accepted within 30 days.",
            read_subjects=[bob.actor],
        )
        hits = runtime.query.retrieve(bob, QueryInput(question="Returns", top_k=1))
        assert len(hits) == 1 and hits[0].document_id == shared["document_id"]
        assert "30 days" in runtime.query.answer(bob, QueryInput(question="Returns"))["answer"]
        for number in range(12):
            runtime.ingestion.enqueue(
                alice,
                DocumentInput(external_id=f"doc-{number}", title="Policy", content="Returns"),
                f"job-{number}",
            )
        with ThreadPoolExecutor(max_workers=6) as executor:
            jobs = list(executor.map(lambda _: repository.claim(60), range(18)))
        claimed = [job for job in jobs if job is not None]
        assert len(claimed) == 12 and len({job["id"] for job in claimed}) == 12
        repository.delete(alice, shared["document_id"])
        assert runtime.query.retrieve(bob, QueryInput(question="Returns")) == []
    finally:
        with repository.engine.connect() as connection:
            ids = (
                connection.execute(
                    repository.docs.select().where(repository.docs.c.tenant == alice.tenant)
                )
                .mappings()
                .all()
            )
        for row in ids:
            repository.delete(alice, row["id"])
        runtime.close()
