# generation

Kind: **replaceable**. Package: `forge_rag.providers`. Default: **on**.

Extractive, OpenAI or Ollama generation.

## Contract and ownership

- Port: Generator.
- Configuration: `GENERATION_PROVIDER, GENERATION_MODEL, OPENAI_API_KEY, OLLAMA_URL, PROVIDER_TIMEOUT_SECONDS`.
- Surface: Grounded statements from selected evidence.
- Data: No answer/conversation persistence.

## Disable, replace or remove

Select extractive/openai/ollama or replace. Keep structured statements with chunk IDs; unknown citations fail closed. Generator-only replacement does not require reindexing.

Follow [the modular plan](../MODULAR_PLAN.md). Keep the catalog/settings/docs aligned, preserve released migrations, and run enabled/disabled plus relevant pipeline and authorization regression tests.
