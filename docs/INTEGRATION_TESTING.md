# Verifying backend integrations

Run commands from the RAG repository root. The unit contracts exercise the
FastAPI gateway with mocked HTTP and the Java gateway with a mock server. These
checks require no external model service:

```sh
uv run --frozen --all-extras pytest tests/test_fastapi_integration.py
```

## Java-to-Python delegation contract

With Java 21 installed, build the integration, then immediately verify its fixture
token using the RAG verifier. The public fixture token expires in 60 seconds:

```powershell
.\integrations\spring-boot\mvnw.cmd -f integrations\spring-boot\pom.xml clean verify
uv run --frozen --all-extras python scripts/check_java_delegation.py
```

On POSIX, replace the first command with
`./integrations/spring-boot/mvnw -f integrations/spring-boot/pom.xml clean verify`.
The token is generated under the ignored Java `target` directory; it uses a
fixture-only key and cannot authenticate to your private service configuration.
If it expires before verification, rerun the Java tests. Never relax token
verification to make a stale fixture pass.

## API, worker and database smoke

After `forge-rag init-env`, start the local Compose stack and run the smoke script:

```sh
docker compose up --build -d rag-api rag-worker
uv run --frozen --all-extras python scripts/smoke_http.py
```

This submits a synthetic document, waits for the separate worker, checks a cited
answer, deletes the document and verifies abstention. Compose supplies the real
PostgreSQL/pgvector database; the providers remain offline.

CI additionally runs `scripts/smoke_fastapi_backend.py` with a pinned version of
the actual FastAPI sibling, using the exact dependency and `PYTHONPATH` shown in
[the workflow](../.github/workflows/ci.yml). It checks login, gateway ingestion,
answer generation, auth-version revocation and deletion. Importing the integration
alone is not a substitute for that authenticated end-to-end check.

Use a disposable Compose database for smoke tests. `docker compose down` stops
the stack while retaining the volume; adding `-v` deletes its local data, so use
that option only when you intend to discard the test database.
