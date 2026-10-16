# chunking

Kind: **replaceable**. Package: `forge_rag.chunking`. Default: **on**.

Bounded chunks with page/offset provenance.

## Contract and ownership

- Port: Chunker.
- Configuration: `CHUNK_CHARS, CHUNK_OVERLAP, MAX_CHUNKS`.
- Surface: Worker splitting and pipeline signature.
- Data: No tables; produces chunk provenance.

## Disable, replace or remove

Replace CharacterChunker in runtime; bump signature and reindex. Preserve bounded size, normalized-text offsets, page provenance and termination.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
