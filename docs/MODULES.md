# Module catalog

| Module | Kind | Default | Port / boundary |
|---|---|---|---|
| [security](modules/security.md) | required | on | Shared Principal and scope dependencies |
| [persistence](modules/persistence.md) | replaceable | on | Repository |
| [ingestion](modules/ingestion.md) | optional | on | IngestionService and Worker consume Extractor/Chunker/Embedder/Repository |
| [chunking](modules/chunking.md) | replaceable | on | Chunker |
| [embedding](modules/embedding.md) | replaceable | on | Embedder |
| [retrieval](modules/retrieval.md) | required | on | QueryService, Repository, Embedder, Generator, optional Reranker |
| [reranking](modules/reranking.md) | optional | off | Reranker |
| [generation](modules/generation.md) | replaceable | on | Generator |
| [pdf](modules/pdf.md) | optional | off | Extractor |
| [evaluation](modules/evaluation.md) | optional | on | Offline runner orchestrates shared ports |
| [telemetry](modules/telemetry.md) | optional | on | ASGI middleware |
| [api-docs](modules/api-docs.md) | optional | on | FastAPI schema/docs configuration |

The composition root selects adapters. Backend integration modules have their own toggles/removal guides under `integrations/`. See [the modular plan](MODULAR_PLAN.md).
