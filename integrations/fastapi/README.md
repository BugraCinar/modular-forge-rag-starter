# FastAPI backend integration

This is a removable gateway module for
[modular-forge-fastapi-starter](https://github.com/BugraCinar/modular-forge-fastapi-starter).
It uses existing dependencies (`httpx`, `PyJWT`, Pydantic Settings); it does not
install RAG workers or model dependencies in the business backend.

1. Install the integration package into your backend environment, keeping it in
   your dependency manifest/lock (or install the wheel attached to the release):

```sh
pip install "git+https://github.com/BugraCinar/modular-forge-rag-starter.git@v1.0.0#subdirectory=integrations/fastapi"
```

   For local development, `pip install -e ../modular-forge-rag-starter/integrations/fastapi`
   works too. If copying the source package beside `src/modular_forge/` instead,
   add it to the backend's Hatch wheel `packages` list; otherwise it will be
   absent from the backend's built wheel.
2. Wrap the existing factory, or call `install(app)` immediately before its return:

```python
from modular_forge.app import create_app as backend_app
from forge_rag_integration import install


def create_app():
    app = backend_app()
    install(app)
    return app
```

3. Configure the backend's private `.env`:

```dotenv
RAG_MODULE_ENABLED=true
RAG_URL=http://127.0.0.1:8090
RAG_ISSUER=forge-fastapi
RAG_AUDIENCE=modular-forge-rag
RAG_DELEGATION_KEY=<the forge-fastapi value from the RAG service DELEGATION_KEYS>
RAG_TIMEOUT_SECONDS=90
```

Use HTTPS or an authenticated encrypted service mesh across machines. Keep the
URL fixed in server configuration. Login through the existing backend, then call
`/api/v1/rag/documents`, `/search`, `/query`, `/documents/{uuid}`, `/jobs/{uuid}`
with its normal bearer token. Ingestion needs `Idempotency-Key` and returns 202;
poll the job until completed before querying. Existing CSRF, current-account
checks and rate limiting remain in the backend. Apply user-level generation
quotas there as well; the global IP limiter alone is not a spend quota.

The default resolver uses immutable `account['id']`, with tenant
`personal:forge-fastapi:<id>` and no groups. Roles, tenant and groups are never
taken from client JSON. Both admin and user accounts have private knowledge.
For organizations, inject `identity_resolver(account)` that reads membership
from your server-side database and returns `RagIdentity(subject, tenant, groups)`.
For a knowledge base shared with Spring, use a canonical tenant and mapped
`issuer:subject` document ACL entries; numeric account IDs alone are not global.

Request/response JSON is the RAG [HTTP contract](../../docs/API.md). Raise the
backend's `MAX_REQUEST_BYTES` deliberately if required for larger document
uploads, keeping its size limit aligned with the RAG service.

Set `RAG_MODULE_ENABLED=false` to remove all integration routes. To physically
remove, delete the install call and package/dependency; no business DB migration is
required. When registering this in the backend's module catalog, add the same
toggle and removal guide. No sibling repository is changed by this starter.
