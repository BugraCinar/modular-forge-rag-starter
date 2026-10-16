# Windows and PowerShell quick start

Open PowerShell in the repository root with a supported Python installation and
`uv` available. These commands use the locked development dependencies and the
offline providers, so no model account is required.

```powershell
uv sync --frozen --all-extras
uv run --frozen --all-extras forge-rag init-env
uv run --frozen --all-extras forge-rag migrate
uv run --frozen --all-extras forge-rag demo
uv run --frozen --all-extras uvicorn forge_rag.app:create_app --factory --host 127.0.0.1 --port 8090
```

In a second terminal at the same repository root:

```powershell
uv run --frozen --all-extras forge-rag worker
```

Use another terminal for `Invoke-RestMethod http://127.0.0.1:8090/health/ready`.
Stop the API and worker with Ctrl+C. Using `uv run` needs no PowerShell activation
script or execution-policy change. `init-env` refuses to replace an existing
`.env`; keep it when restarting. Relative SQLite paths and `.env` resolve from
the current directory.

The demo creates its own in-memory index. Documents submitted to the running API
need the separate worker and use the configured database. Development `/docs`
is available on port 8090; protected routes require backend delegation, not a
normal user JWT. Use one of the [backend integrations](../integrations/) for
client-facing access.

Docker Compose is an alternative when Docker is available. Do not run the local
API and Compose API on the same port simultaneously. When pointing containers
at a desktop model server, configure a reachable `OLLAMA_URL`; container
`127.0.0.1` refers to that container. See [operations](OPERATIONS.md).
