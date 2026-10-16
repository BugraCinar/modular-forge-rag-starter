# embedding

Kind: **replaceable**. Package: `forge_rag.providers`. Default: **on**.

Hash, OpenAI or Ollama embeddings.

## Contract and ownership

- Port: Embedder.
- Configuration: `EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_REVISION, EMBEDDING_DIMENSIONS`.
- Surface: Worker batches and question embedding.
- Data: Vectors owned by Repository.

## Disable, replace or remove

Select hash/openai/ollama, or replace port. Only selected adapters load. Changing implementation/model/dimensions requires reingestion and signature change.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
