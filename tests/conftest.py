import base64

import pytest
from fastapi.testclient import TestClient

from forge_rag.app import create_app
from forge_rag.persistence.store import SQLRepository
from forge_rag.security.delegation import issue_token
from forge_rag.shared.config import Settings
from forge_rag.shared.models import Principal

KEY = bytes(range(32))
OTHER_KEY = bytes(range(32, 64))


@pytest.fixture
def account():
    return Principal("forge-fastapi", "alice", "tenant-a")


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'rag.db').as_posix()}",
        delegation_keys={
            "forge-fastapi": base64.b64encode(KEY).decode(),
            "forge-spring": base64.b64encode(OTHER_KEY).decode(),
        },
    )


@pytest.fixture
def service(settings):
    repository = SQLRepository(settings)
    repository.migrate()
    app = create_app(settings, repository=repository)
    with TestClient(app) as client:
        yield app.state.rag, client


def auth(account):
    return {
        "Authorization": "Bearer "
        + issue_token(KEY if account.issuer == "forge-fastapi" else OTHER_KEY, account)
    }


def ingest(
    runtime,
    account,
    *,
    external_id="policy",
    text="Returns are accepted within 30 days.",
    key="document-1",
    **kwargs,
):
    from forge_rag.shared.models import DocumentInput

    job = runtime.ingestion.enqueue(
        account, DocumentInput(external_id=external_id, title="Policy", content=text, **kwargs), key
    )
    runtime.worker.once()
    return job
