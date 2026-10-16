# pdf

Kind: **optional**. Package: `forge_rag.pdf`. Default: **off**.

PDF text layer extractor; no OCR.

## Contract and ownership

- Port: Extractor.
- Configuration: `MODULE_PDF_ENABLED; pdf dependency extra`.
- Surface: PDF media type on document ingestion.
- Data: No extra tables; queued Base64 payload then text chunks.

## Disable, replace or remove

Off by default; disabled means 415 before enqueue and no pypdf import. Remove PDF branch/package/extra. No OCR. Keep workers isolated for parser resource limits.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
