from sqlalchemy import select, update

from forge_rag.shared.errors import ProviderError
from forge_rag.shared.models import DocumentInput, Piece, QueryInput
from tests.conftest import ingest


def queue(runtime, account, key="one", content="Returns in 30 days."):
    return runtime.ingestion.enqueue(
        account, DocumentInput(external_id="policy", title="Policy", content=content), key
    )


def test_expired_lease_cannot_publish(service, account):
    runtime, _ = service
    queue(runtime, account)
    repository = runtime.repository
    first = repository.claim(60)
    assert repository.renew(first, 90)
    assert repository.claim(60) is None
    with repository.engine.begin() as connection:
        connection.execute(update(repository.jobs).values(lease_until=0))
    second = repository.claim(60)
    assert not repository.renew(first, 90)
    assert first["lease_token"] != second["lease_token"]
    pieces, vectors = [Piece("Returns", 0, 0, 7)], [[1.0] * 256]
    assert not repository.publish(first, pieces, vectors)
    assert repository.publish(second, pieces, vectors)
    assert not repository.renew(second, 90)


def test_stale_revision_and_deleted_jobs_cannot_publish(service, account):
    runtime, _ = service
    first = queue(runtime, account)
    old = runtime.repository.claim(60)
    queue(runtime, account, "two", "Returns in 60 days.")
    assert not runtime.repository.publish(old, [Piece("old", 0, 0, 3)], [[1.0] * 256])
    newest = runtime.repository.claim(60)
    runtime.repository.delete(account, first["document_id"])
    assert not runtime.repository.publish(newest, [Piece("deleted", 0, 0, 7)], [[1.0] * 256])


def test_provider_failure_retry_and_terminal_scrub(service, account):
    runtime, _ = service
    job = queue(runtime, account)

    class FailingEmbedder:
        dimensions = 256
        signature = "failure"

        def embed(self, texts):
            raise ProviderError("sensitive document and credentials must not appear in storage")

    runtime.worker.embedder = FailingEmbedder()
    for _ in range(3):
        assert runtime.worker.once()
        with runtime.repository.engine.begin() as connection:
            connection.execute(update(runtime.repository.jobs).values(available_at=0))
    status = runtime.repository.job(account, job["id"])
    assert status["status"] == "failed" and status["attempts"] == 3
    assert status["error_code"] == "provider_unavailable"
    with runtime.repository.engine.connect() as connection:
        assert connection.execute(select(runtime.repository.jobs.c.payload)).scalar_one() == {}


def test_pipeline_change_fails_without_embedding(service, account):
    runtime, _ = service
    job = queue(runtime, account)
    runtime.worker.signature = "new-config"
    runtime.worker.once()
    assert runtime.repository.job(account, job["id"])["error_code"] == "pipeline_changed"


def test_invalid_extraction_is_permanent(service, account):
    runtime, _ = service
    job = queue(runtime, account, content="\x00binary")
    runtime.worker.once()
    status = runtime.repository.job(account, job["id"])
    assert status["status"] == "failed" and status["attempts"] == 1


def test_restart_keeps_pending_job(settings, account):
    from forge_rag.persistence.store import SQLRepository
    from forge_rag.runtime import build_runtime

    repo = SQLRepository(settings)
    repo.migrate()
    runtime = build_runtime(settings, repository=repo)
    job = queue(runtime, account)
    runtime.close()
    replacement = build_runtime(settings)
    try:
        replacement.worker.once()
        assert replacement.repository.job(account, job["id"])["status"] == "completed"
        assert replacement.query.retrieve(account, QueryInput(question="Returns"))
    finally:
        replacement.close()


def test_terminal_job_retention(service, account):
    runtime, _ = service
    ingest(runtime, account)
    assert runtime.repository.purge_jobs(0) == 0
    assert runtime.repository.purge_jobs(10**12) == 1
