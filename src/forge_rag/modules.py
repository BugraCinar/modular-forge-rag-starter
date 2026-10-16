CATALOG = [
    ("security", "required", None, "security", "Backend delegation and HTTP boundaries"),
    ("persistence", "replaceable", None, "persistence", "Metadata, ACLs, jobs and vector storage"),
    (
        "ingestion",
        "optional",
        "module_ingestion_enabled",
        "ingestion",
        "Document API and durable worker",
    ),
    (
        "chunking",
        "replaceable",
        None,
        "chunking",
        "Bounded chunks with page/offset provenance",
    ),
    ("embedding", "replaceable", None, "providers", "Hash, OpenAI or Ollama embeddings"),
    (
        "retrieval",
        "required",
        None,
        "retrieval",
        "Authorized hybrid retrieval and grounded query API",
    ),
    (
        "reranking",
        "optional",
        "module_reranking_enabled",
        "reranking",
        "Replaceable candidate reranker",
    ),
    ("generation", "replaceable", None, "providers", "Extractive, OpenAI or Ollama generation"),
    ("pdf", "optional", "module_pdf_enabled", "pdf", "PDF text layer extractor; no OCR"),
    (
        "evaluation",
        "optional",
        "module_evaluation_enabled",
        "evaluation",
        "Offline retrieval and citation regression suite",
    ),
    (
        "telemetry",
        "optional",
        "module_telemetry_enabled",
        "telemetry",
        "Request metadata without source content",
    ),
    ("api-docs", "optional", "module_api_docs_enabled", "app", "Development OpenAPI documentation"),
]


def catalog(settings):
    return [
        {
            "id": identifier,
            "kind": kind,
            "enabled": getattr(settings, toggle) if toggle else True,
            "package": package,
            "description": description,
        }
        for identifier, kind, toggle, package, description in CATALOG
    ]
