from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from forge_rag import __version__
from forge_rag.modules import catalog
from forge_rag.runtime import build_runtime
from forge_rag.security.dependencies import reader
from forge_rag.security.middleware import BoundaryMiddleware
from forge_rag.shared.config import Settings
from forge_rag.shared.errors import RagError
from forge_rag.shared.models import QueryInput


def create_app(settings: Settings | None = None, *, repository=None, embedder=None, generator=None):
    settings = settings or Settings()
    runtime = build_runtime(settings, repository=repository, embedder=embedder, generator=generator)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            runtime.close()

    app = FastAPI(
        title="Modular Forge RAG",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.module_api_docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.module_api_docs_enabled else None,
    )
    app.state.rag = runtime

    @app.exception_handler(RagError)
    async def rag_error(request: Request, exc: RagError):
        return JSONResponse(
            {
                "error": {"code": exc.code, "message": exc.message},
                "request_id": request.state.request_id,
            },
            status_code=exc.status,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request.",
                    "fields": [
                        {"location": list(item["loc"]), "type": item["type"]}
                        for item in exc.errors()
                    ],
                },
                "request_id": request.state.request_id,
            },
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        return JSONResponse(
            {
                "error": {"code": "internal_error", "message": "Request could not be completed."},
                "request_id": getattr(request.state, "request_id", ""),
            },
            status_code=500,
        )

    @app.get("/health/live", tags=["Health"])
    def live():
        return {"status": "up"}

    @app.get("/health/ready", tags=["Health"])
    def ready():
        healthy = runtime.repository.ready()
        return JSONResponse(
            {"status": "up" if healthy else "down"}, status_code=200 if healthy else 503
        )

    @app.get("/v1/modules", tags=["Modules"])
    def modules(account=Depends(reader)):
        return catalog(settings)

    @app.post("/v1/search", tags=["Retrieval"])
    def search(payload: QueryInput, account=Depends(reader)):
        return runtime.query.search(account, payload)

    @app.post("/v1/query", tags=["Retrieval"])
    def answer(payload: QueryInput, account=Depends(reader)):
        return runtime.query.answer(account, payload)

    if settings.module_ingestion_enabled:
        from forge_rag.ingestion.routes import router

        app.include_router(router)
    if settings.module_telemetry_enabled:
        from forge_rag.telemetry.middleware import TelemetryMiddleware

        app.add_middleware(TelemetryMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(BoundaryMiddleware, maximum=settings.max_document_bytes * 2 + 16384)
    return app
