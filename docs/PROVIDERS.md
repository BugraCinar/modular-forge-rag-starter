# Embedding and generation adapters

Default providers make no network calls: `hash` is a deterministic lexical test
vector and `extractive` selects sentences from evidence. They exist to verify
the pipeline and isolation on a laptop; they do not provide semantic QA quality.

## OpenAI

```dotenv
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=256
GENERATION_PROVIDER=openai
GENERATION_MODEL=<your explicitly selected Responses model with structured outputs>
OPENAI_API_KEY=<private project key>
```

The embedding adapter calls `/v1/embeddings` with float output and explicit
dimensions. The documented `text-embedding-3` family supports the dimensions
parameter; another model must be checked for compatibility before use.
Generation calls `/v1/responses` with a strict JSON schema, output budget and
`store:false`. No tools, file search or conversation storage are requested.
Refusal/empty statements abstain; incomplete/invalid outputs fail closed.

Official references: [embeddings endpoint](https://developers.openai.com/api/reference/resources/embeddings/methods/create),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses),
[text generation](https://developers.openai.com/api/docs/guides/text).
`store:false` controls response storage; it does not promise zero provider
retention or remove your obligations under the provider's data policy.

No paid calls are made by demo, evaluation, tests or CI. Provider adapters use
mock HTTP contracts. Real model access, output quality and account-specific
limits must be validated in your environment. Keep project budgets and tenant
quotas outside the model prompt; a prompt cannot enforce a spending limit.

## Ollama

Set `EMBEDDING_PROVIDER=ollama`, `GENERATION_PROVIDER=ollama`, and explicitly choose
your installed embedding/generation models. Set `EMBEDDING_DIMENSIONS` to the
embedding model's real dimension; mismatches fail indexing/query. Models are
never downloaded by this service.

`OLLAMA_URL` is a fixed server-controlled origin. `/api/embed` uses
`truncate:false`; `/api/generate` uses JSON schema, `stream:false`, temperature 0
and `num_predict=1200`. Set an appropriate provider timeout. Production mode
requires HTTPS, normally via an internal TLS reverse proxy.

Official references: [embedding API](https://docs.ollama.com/api/embed),
[generation API](https://docs.ollama.com/api/generate),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
For local Docker Compose, point `OLLAMA_URL` at a reachable model host and pass
it to both API and worker. `127.0.0.1` inside a container is that container,
not your desktop. Keep a model server private.

## Replacement and model changes

Implement `Embedder` (`signature`, `dimensions`, `embed`) or `Generator`
(`generate`) from `shared/ports.py` and select it in `runtime.py`. For tests, the
app factory/runtime builder accepts injected adapters. No provider-specific
imports belong in ingestion/retrieval domain services. HTTP clients have finite
timeouts, no redirects or inherited proxy environment, and return generic errors.

Embedding configuration is shared by API and worker. Model/dimension/chunk/
extractor changes need reingestion with new idempotency keys. Increment
`EMBEDDING_REVISION` when an alias keeps the same name but its weights or your
adapter implementation changes. An old worker rejects incompatible queued jobs.
Generator-only changes can reuse the existing evidence index.

Chunks are at most 1500 Unicode characters and batches contain 32 chunks. This
is a conservative bound for the documented embedding input limit, rather than
a tokenizer-aware splitter. Tune and replace the chunker for tables, code,
long-document hierarchy or a provider with tighter token limits.
